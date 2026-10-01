import json
import sys
import unittest
from pathlib import Path

import httpx


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.client import (  # noqa: E402
    AmisClient,
    AmisConfigurationError,
    AmisContractError,
)
from domains.amis.config import AmisConfig  # noqa: E402


class AmisClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_all_paginates_and_sends_required_headers(self):
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            if request.url.path.endswith("/Account"):
                return httpx.Response(200, json={"success": True, "data": "token-1"})
            self.assertEqual(request.headers["Authorization"], "Bearer token-1")
            self.assertEqual(request.headers["Clientid"], "JavisCFCChatbot")
            page = int(request.url.params["page"])
            records = (
                [{"account_number": "KH1"}, {"account_number": "KH2"}]
                if page == 0
                else [{"account_number": "KH3"}]
            )
            return httpx.Response(200, json={"success": True, "data": records})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = AmisClient(
                AmisConfig(
                    client_id="JavisCFCChatbot",
                    client_secret="secret",
                    page_size=2,
                ),
                http_client=http_client,
                sleep=self._no_sleep,
            )
            records = await client.fetch_all("customers")

        self.assertEqual([record["account_number"] for record in records], ["KH1", "KH2", "KH3"])
        self.assertEqual(len(seen), 3)

    async def test_401_refreshes_token_once(self):
        token_calls = 0
        data_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal token_calls, data_calls
            if request.url.path.endswith("/Account"):
                token_calls += 1
                return httpx.Response(200, json={"success": True, "data": f"token-{token_calls}"})
            data_calls += 1
            if data_calls == 1:
                return httpx.Response(401, json={"success": False})
            self.assertEqual(request.headers["Authorization"], "Bearer token-2")
            return httpx.Response(200, json={"success": True, "data": []})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = AmisClient(
                AmisConfig(client_id="app", client_secret="secret"),
                http_client=http_client,
                sleep=self._no_sleep,
            )
            self.assertEqual(await client.fetch_all("products"), [])

        self.assertEqual(token_calls, 2)
        self.assertEqual(data_calls, 2)

    async def test_repeated_full_page_is_rejected(self):
        records = [{"id": 1}, {"id": 2}]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/Account"):
                return httpx.Response(200, json={"success": True, "data": "token"})
            return httpx.Response(200, json={"success": True, "data": records})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = AmisClient(
                AmisConfig(client_id="app", client_secret="secret", page_size=2, max_pages=3),
                http_client=http_client,
                sleep=self._no_sleep,
            )
            with self.assertRaises(AmisContractError):
                await client.fetch_all("sale_orders")

    async def test_missing_secret_fails_before_network_request(self):
        def handler(_: httpx.Request) -> httpx.Response:
            self.fail("network should not be called")

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = AmisClient(
                AmisConfig(client_id="app", client_secret=""),
                http_client=http_client,
            )
            with self.assertRaises(AmisConfigurationError):
                await client.fetch_all("customers")

    @staticmethod
    async def _no_sleep(_: float) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
