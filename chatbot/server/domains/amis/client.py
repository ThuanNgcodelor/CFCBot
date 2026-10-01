"""Minimal read-only client for MISA AMIS CRM Open API v2."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Awaitable, Callable, Optional

import httpx

from .config import AmisConfig


class AmisError(RuntimeError):
    """Base error for the AMIS integration."""


class AmisConfigurationError(AmisError):
    """Raised when required credentials are missing."""


class AmisApiError(AmisError):
    """Raised when AMIS rejects or cannot process a request."""


class AmisContractError(AmisError):
    """Raised when the response shape is unsafe or unsupported."""


class AmisClient:
    READ_RESOURCES = {
        "customers": "/Customers",
        "products": "/Products",
        "sale_orders": "/SaleOrders",
    }

    def __init__(
        self,
        config: AmisConfig,
        *,
        http_client: Optional[httpx.AsyncClient] = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.config = config
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=config.timeout_seconds,
            follow_redirects=False,
        )
        self._sleep = sleep
        self._token = ""

    async def __aenter__(self) -> "AmisClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    @staticmethod
    def _json(response: httpx.Response, path: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AmisContractError(f"AMIS returned invalid JSON for {path}") from exc
        if not isinstance(payload, dict):
            raise AmisContractError(f"AMIS returned a non-object payload for {path}")
        return payload

    async def _authenticate(self, *, force: bool = False) -> str:
        if self._token and not force:
            return self._token
        if not self.config.credentials_configured:
            raise AmisConfigurationError(
                "AMIS_CLIENT_ID and AMIS_CLIENT_SECRET must be configured"
            )

        for attempt in range(self.config.max_retries):
            response = await self._http.post(
                self._url("/Account"),
                headers={"Content-Type": "application/json"},
                json={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < self.config.max_retries:
                    await self._sleep(min(2 ** attempt, 5))
                    continue
            if response.status_code >= 400:
                raise AmisApiError(f"AMIS authentication failed with HTTP {response.status_code}")

            payload = self._json(response, "/Account")
            if payload.get("success") is False:
                raise AmisApiError("AMIS authentication was rejected")
            data = payload.get("data")
            token = ""
            if isinstance(data, str):
                token = data
            elif isinstance(data, dict):
                token = data.get("access_token", "")
            if not token:
                raise AmisContractError("AMIS authentication response did not include a token")
            self._token = str(token)
            return self._token

        raise AmisApiError("AMIS authentication retry limit reached")

    async def _get_page(self, path: str, *, page: int) -> dict[str, Any]:
        refreshed = False
        for attempt in range(self.config.max_retries):
            token = await self._authenticate(force=refreshed)
            response = await self._http.get(
                self._url(path),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Clientid": self.config.client_id,
                    "Accept": "application/json",
                },
                params={
                    "page": page,
                    "pageSize": self.config.page_size,
                    "orderBy": "modified_date",
                    "isDescending": "true",
                },
            )
            if response.status_code == 401 and not refreshed:
                self._token = ""
                refreshed = True
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < self.config.max_retries:
                    await self._sleep(min(2 ** attempt, 5))
                    continue
            if response.status_code >= 400:
                raise AmisApiError(f"AMIS GET {path} failed with HTTP {response.status_code}")

            payload = self._json(response, path)
            if payload.get("success") is False:
                raise AmisApiError(f"AMIS GET {path} was rejected")
            return payload

        raise AmisApiError(f"AMIS GET {path} retry limit reached")

    @staticmethod
    def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidates: list[Any] = [payload.get("data")]
        data = payload.get("data")
        if isinstance(data, dict):
            candidates.extend(data.get(key) for key in ("items", "data", "records", "results"))
        candidates.extend(payload.get(key) for key in ("items", "records", "results"))

        for candidate in candidates:
            if isinstance(candidate, list):
                if not all(isinstance(item, dict) for item in candidate):
                    raise AmisContractError("AMIS record list contains non-object items")
                return candidate
        return []

    @staticmethod
    def _total(payload: dict[str, Any]) -> Optional[int]:
        containers = [payload, payload.get("data")]
        for container in containers:
            if not isinstance(container, dict):
                continue
            for key in ("total", "total_count", "totalCount", "count"):
                try:
                    value = int(container.get(key))
                except (TypeError, ValueError):
                    continue
                if value >= 0:
                    return value
        return None

    @staticmethod
    def _page_fingerprint(records: list[dict[str, Any]]) -> str:
        if not records:
            return "empty"
        sample = [records[0], records[-1], {"length": len(records)}]
        raw = json.dumps(sample, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def fetch_all(self, resource: str) -> list[dict[str, Any]]:
        path = self.READ_RESOURCES.get(resource)
        if not path:
            raise ValueError(f"Unsupported AMIS read resource: {resource}")

        collected: list[dict[str, Any]] = []
        fingerprints: set[str] = set()
        for page in range(self.config.max_pages):
            payload = await self._get_page(path, page=page)
            records = self._records(payload)
            if not records:
                return collected

            fingerprint = self._page_fingerprint(records)
            if fingerprint in fingerprints:
                raise AmisContractError(f"AMIS pagination repeated page data for {resource}")
            fingerprints.add(fingerprint)
            collected.extend(records)

            total = self._total(payload)
            if total is not None and len(collected) >= total:
                return collected[:total]
            if len(records) < self.config.page_size:
                return collected

        raise AmisContractError(f"AMIS pagination exceeded max_pages for {resource}")

    async def fetch_public_source_datasets(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "products": await self.fetch_all("products"),
            "customers": await self.fetch_all("customers"),
            "sale_orders": await self.fetch_all("sale_orders"),
        }
