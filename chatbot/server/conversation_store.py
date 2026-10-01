"""Consistent conversation persistence and bounded in-process caches."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
import secrets
import time
from typing import Any, AsyncIterator, Generic, Iterator, MutableMapping, Optional, TypeVar


T = TypeVar("T")


class BoundedTTLCache(MutableMapping[str, T], Generic[T]):
    """Small dict-compatible TTL/LRU cache used by the legacy pipeline."""

    def __init__(self, *, maxsize: int = 5000, ttl_seconds: float = 3600.0) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()

    def _expired(self, stored_at: float) -> bool:
        return (time.monotonic() - stored_at) >= self.ttl_seconds

    def _purge(self) -> None:
        expired = [key for key, (stored_at, _) in self._items.items() if self._expired(stored_at)]
        for key in expired:
            self._items.pop(key, None)
        while len(self._items) > self.maxsize:
            self._items.popitem(last=False)

    def __getitem__(self, key: str) -> T:
        stored_at, value = self._items[key]
        if self._expired(stored_at):
            del self._items[key]
            raise KeyError(key)
        self._items.move_to_end(key)
        return value

    def __setitem__(self, key: str, value: T) -> None:
        self._items[key] = (time.monotonic(), value)
        self._items.move_to_end(key)
        self._purge()

    def __delitem__(self, key: str) -> None:
        del self._items[key]

    def __iter__(self) -> Iterator[str]:
        self._purge()
        return iter(self._items)

    def __len__(self) -> int:
        self._purge()
        return len(self._items)

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        try:
            return self[key]
        except KeyError:
            return default

    def clear(self) -> None:
        self._items.clear()


@dataclass(frozen=True)
class ConversationStoreConfig:
    session_ttl_seconds: int = 30 * 24 * 60 * 60
    history_ttl_seconds: int = 30 * 24 * 60 * 60
    history_limit: int = 50
    sender_lock_ttl_seconds: int = 30
    sender_lock_wait_seconds: float = 3.0


async def load_json(redis_client: Any, key: str) -> dict[str, Any]:
    try:
        raw = await redis_client.get(key)
    except Exception:
        return {}
    if not isinstance(raw, (str, bytes)) or not raw:
        return {}
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


async def persist_session(
    redis_client: Any,
    *,
    session_key: str,
    history_key: str,
    session_data: dict[str, Any],
    history_record: dict[str, Any],
    config: ConversationStoreConfig = ConversationStoreConfig(),
) -> None:
    """Persist the current state before returning to the webhook caller."""
    session_payload = json.dumps(session_data, ensure_ascii=False)
    history_payload = json.dumps(history_record, ensure_ascii=False)

    pipeline_factory = getattr(redis_client, "pipeline", None)
    if callable(pipeline_factory):
        pipeline = pipeline_factory(transaction=True)
        pipeline.set(session_key, session_payload, ex=config.session_ttl_seconds)
        pipeline.rpush(history_key, history_payload)
        pipeline.ltrim(history_key, -config.history_limit, -1)
        pipeline.expire(history_key, config.history_ttl_seconds)
        await pipeline.execute()
        return

    try:
        await redis_client.set(session_key, session_payload, ex=config.session_ttl_seconds)
    except TypeError:
        await redis_client.set(session_key, session_payload)
        expire = getattr(redis_client, "expire", None)
        if callable(expire):
            await expire(session_key, config.session_ttl_seconds)
    await redis_client.rpush(history_key, history_payload)
    await redis_client.ltrim(history_key, -config.history_limit, -1)
    expire = getattr(redis_client, "expire", None)
    if callable(expire):
        await expire(history_key, config.history_ttl_seconds)


async def _try_acquire_lease(redis_client: Any, key: str, token: str, ttl_seconds: int) -> Optional[bool]:
    try:
        result = await redis_client.set(key, token, nx=True, ex=ttl_seconds)
    except Exception:
        return None
    return bool(result)


async def _release_lease(redis_client: Any, key: str, token: str) -> None:
    script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    end
    return 0
    """
    try:
        await redis_client.eval(script, 1, key, token)
        return
    except Exception:
        pass
    try:
        current = await redis_client.get(key)
        if current == token or (isinstance(current, bytes) and current.decode() == token):
            await redis_client.delete(key)
    except Exception:
        return


@asynccontextmanager
async def sender_lease(
    redis_client: Any,
    *,
    brand: str,
    sender_id: str,
    config: ConversationStoreConfig = ConversationStoreConfig(),
) -> AsyncIterator[bool]:
    """Serialize different messages for one sender across worker processes."""
    key = f"{brand}:chat:sender-lock:{sender_id}"
    token = secrets.token_urlsafe(18)
    deadline = time.monotonic() + config.sender_lock_wait_seconds
    acquired = False
    while time.monotonic() < deadline:
        lease_result = await _try_acquire_lease(redis_client, key, token, config.sender_lock_ttl_seconds)
        if lease_result is None:
            break
        acquired = lease_result
        if acquired:
            break
        await asyncio.sleep(0.04)
    try:
        yield acquired
    finally:
        if acquired:
            await _release_lease(redis_client, key, token)
