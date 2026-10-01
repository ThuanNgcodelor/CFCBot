"""
domains.common.db — Quản lý kết nối Redis Async và HTTP Client tới n8n.
"""

import httpx
import redis.asyncio as aioredis
from typing import Optional
from .config import get_cfg


def get_redis_client(decode: bool = True) -> aioredis.Redis:
    """Tạo client Redis Async theo cấu hình hiện hành."""
    c = get_cfg().get("redis", {})
    return aioredis.Redis(
        host=c.get("host", "127.0.0.1"),
        port=int(c.get("port", 6379)),
        password=c.get("password", "") or None,
        db=int(c.get("db", 0)),
        decode_responses=decode,
    )


def get_n8n_config() -> dict:
    """Lấy cấu hình n8n URL và API Key."""
    return get_cfg().get("n8n", {"url": "https://n8n.dinhduongcantho.io.vn", "api_key": ""})


async def n8n_request(method: str, path: str, body: dict = None, timeout: float = 10.0) -> httpx.Response:
    """Thực hiện HTTP request tới n8n REST API v1."""
    n8n = get_n8n_config()
    headers = {
        "Content-Type": "application/json",
        "X-N8N-API-KEY": n8n.get("api_key", ""),
    }
    url = f"{n8n['url']}/api/v1{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body or {})
        elif method == "PATCH":
            resp = await client.patch(url, headers=headers, json=body or {})
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unknown HTTP method: {method}")
    return resp
