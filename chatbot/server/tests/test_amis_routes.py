import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.routes import _require_internal, amis_status  # noqa: E402


def request_from(host: str):
    return SimpleNamespace(client=SimpleNamespace(host=host))


class AmisRouteSecurityTests(unittest.IsolatedAsyncioTestCase):
    def test_loopback_is_allowed_when_internal_token_is_not_configured(self):
        config = AmisConfig(internal_token="")
        with patch("domains.amis.routes.load_amis_config", return_value=config):
            _require_internal(request_from("127.0.0.1"))

    def test_external_host_is_rejected_without_internal_token(self):
        config = AmisConfig(internal_token="")
        with patch("domains.amis.routes.load_amis_config", return_value=config):
            with self.assertRaises(HTTPException) as raised:
                _require_internal(request_from("203.0.113.10"))

        self.assertEqual(raised.exception.status_code, 403)

    def test_configured_internal_token_is_required_for_every_host(self):
        config = AmisConfig(internal_token="sync-token")
        with patch("domains.amis.routes.load_amis_config", return_value=config):
            with self.assertRaises(HTTPException):
                _require_internal(request_from("127.0.0.1"), "wrong-token")
            _require_internal(request_from("203.0.113.10"), "sync-token")

    async def test_status_never_exposes_secret_or_internal_token(self):
        config = AmisConfig(
            client_id="JavisCFCChatbot",
            client_secret="crm-secret",
            internal_token="sync-token",
        )
        with patch("domains.amis.routes.load_amis_config", return_value=config):
            result = await amis_status(request_from("203.0.113.10"), "sync-token")

        encoded = str(result)
        self.assertNotIn("crm-secret", encoded)
        self.assertNotIn("sync-token", encoded)
        self.assertTrue(result["config"]["credentials_configured"])
        self.assertTrue(result["config"]["internal_token_configured"])


if __name__ == "__main__":
    unittest.main()
