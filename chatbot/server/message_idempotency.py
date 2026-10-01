"""Redis-backed Messenger message idempotency."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Optional


@dataclass(frozen=True)
class IdempotencyDecision:
    status: str
    cached_response: Optional[dict[str, Any]] = None
    lease_key: str = ""
    response_key: str = ""
    token: str = ""


def _key_suffix(message_id: str) -> str:
    return hashlib.sha256(message_id.encode("utf-8")).hexdigest()


def _keys(brand: str, message_id: str) -> tuple[str, str]:
    suffix = _key_suffix(message_id)
    base = f"{brand}:chat:idempotency:{suffix}"
    return f"{base}:lease", f"{base}:response"


async def begin_message(
    redis_client: Any,
    *,
    brand: str,
    message_id: str,
    lease_ttl_seconds: int = 30,
) -> IdempotencyDecision:
    if not message_id:
        return IdempotencyDecision(status="disabled")

    lease_key, response_key = _keys(brand, message_id)
    try:
        cached = await redis_client.get(response_key)
        if isinstance(cached, (str, bytes)) and cached:
            value = json.loads(cached)
            if isinstance(value, dict):
                return IdempotencyDecision(status="cached", cached_response=value)

        token = hashlib.sha256(f"{brand}:{message_id}".encode("utf-8")).hexdigest()
        acquired = await redis_client.set(lease_key, token, nx=True, ex=lease_ttl_seconds)
        if acquired:
            return IdempotencyDecision(
                status="acquired",
                lease_key=lease_key,
                response_key=response_key,
                token=token,
            )
        return IdempotencyDecision(status="in_flight")
    except Exception:
        return IdempotencyDecision(status="degraded")


async def complete_message(
    redis_client: Any,
    decision: IdempotencyDecision,
    response: dict[str, Any],
    *,
    response_ttl_seconds: int = 24 * 60 * 60,
) -> None:
    if decision.status != "acquired":
        return
    payload = json.dumps(response, ensure_ascii=False)
    try:
        await redis_client.set(decision.response_key, payload, ex=response_ttl_seconds)
    finally:
        await release_message(redis_client, decision)


async def release_message(redis_client: Any, decision: IdempotencyDecision) -> None:
    if decision.status != "acquired":
        return
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """
    try:
        await redis_client.eval(script, 1, decision.lease_key, decision.token)
        return
    except Exception:
        pass
    try:
        current = await redis_client.get(decision.lease_key)
        if current == decision.token or (isinstance(current, bytes) and current.decode() == decision.token):
            await redis_client.delete(decision.lease_key)
    except Exception:
        return
