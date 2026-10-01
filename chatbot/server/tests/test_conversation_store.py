import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from conversation_store import (  # noqa: E402
    BoundedTTLCache,
    ConversationStoreConfig,
    persist_session,
    sender_lease,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.expirations = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    async def delete(self, key):
        self.values.pop(key, None)

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        self.lists[key] = values[start:] if start < 0 else values[start:end + 1]

    async def expire(self, key, seconds):
        self.expirations[key] = seconds

    async def eval(self, script, count, key, token):
        if self.values.get(key) == token:
            await self.delete(key)
            return 1
        return 0


class BoundedTTLCacheTests(unittest.TestCase):
    def test_cache_expires_and_evicts_oldest_item(self):
        with patch("conversation_store.time.monotonic", return_value=10.0):
            cache = BoundedTTLCache(maxsize=2, ttl_seconds=5)
            cache["a"] = {"value": 1}
            cache["b"] = {"value": 2}
        with patch("conversation_store.time.monotonic", return_value=11.0):
            cache["c"] = {"value": 3}
            self.assertIsNone(cache.get("a"))
            self.assertEqual(cache["c"]["value"], 3)
        with patch("conversation_store.time.monotonic", return_value=20.0):
            self.assertIsNone(cache.get("b"))
            self.assertEqual(len(cache), 0)


class ConversationStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_persist_session_sets_ttl_and_bounded_history(self):
        redis_client = FakeRedis()
        config = ConversationStoreConfig(
            session_ttl_seconds=100,
            history_ttl_seconds=200,
            history_limit=2,
        )
        for revision in range(3):
            await persist_session(
                redis_client,
                session_key="session",
                history_key="history",
                session_data={"revision": revision},
                history_record={"revision": revision},
                config=config,
            )

        self.assertEqual(json.loads(redis_client.values["session"])["revision"], 2)
        self.assertEqual(len(redis_client.lists["history"]), 2)
        self.assertEqual(redis_client.expirations["session"], 100)
        self.assertEqual(redis_client.expirations["history"], 200)

    async def test_sender_lease_releases_only_its_lock(self):
        redis_client = FakeRedis()
        async with sender_lease(redis_client, brand="zeo", sender_id="sender") as acquired:
            self.assertTrue(acquired)
            self.assertIn("zeo:chat:sender-lock:sender", redis_client.values)
        self.assertNotIn("zeo:chat:sender-lock:sender", redis_client.values)

    async def test_sender_lease_fails_open_immediately_when_redis_is_down(self):
        class BrokenRedis:
            async def set(self, *args, **kwargs):
                raise ConnectionError("redis down")

        with patch("conversation_store.asyncio.sleep", new_callable=AsyncMock) as sleep:
            async with sender_lease(BrokenRedis(), brand="zeo", sender_id="sender") as acquired:
                self.assertFalse(acquired)
        sleep.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
