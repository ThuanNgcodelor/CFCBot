import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import knowledge_sync  # noqa: E402
import rag_search  # noqa: E402


CFG = {
    "redis": {"host": "localhost", "port": 6379, "password": "", "db": 0},
    "rag": {
        "zeo_kb_key": "zeo:kb:basic:active",
        "cfc_kb_key": "cfc:kb:basic:active",
        "zeo_index_name": "zeo:vec:faq",
        "cfc_index_name": "cfc:vec:faq",
    },
}


class FakeRedis:
    def __init__(self, snapshot=None, stale_keys=None):
        self.snapshot = snapshot
        self.stale_keys = list(stale_keys or [])
        self.hsets = []
        self.deletes = []
        self.commands = []
        self.gets = []
        self.closed = False

    async def get(self, key):
        self.gets.append(key)
        return self.snapshot

    async def execute_command(self, *args):
        self.commands.append(args)
        return {}

    async def hset(self, key, mapping):
        self.hsets.append((key, mapping))

    async def delete(self, key):
        self.deletes.append(key)

    async def aclose(self):
        self.closed = True

    async def scan_iter(self, **_kwargs):
        for key in self.stale_keys:
            yield key


def _snapshot(*items):
    return json.dumps(list(items), ensure_ascii=False).encode("utf-8")


def _active_item(intent="faq_one"):
    return {
        "intent": intent,
        "answer": "Câu trả lời đã duyệt",
        "source_id": "test:faq",
        "active": True,
        "audience": "customer",
        "question_examples": "hỏi một; hỏi hai",
    }


class KnowledgeSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_requires_vector_and_hot_cache_checkpoints(self):
        fake = FakeRedis(_snapshot(_active_item()))
        refresh = AsyncMock(return_value={"status": "ok", "brands": {"cfc": {"source": "redis"}}})
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", return_value=fake), \
                patch("knowledge_sync.get_embed_dim", return_value=3), \
                patch("knowledge_sync.embed_text", new=AsyncMock(return_value=[0.1, 0.2, 0.3])), \
                patch("knowledge_sync.vec_to_bytes", return_value=b"vec"), \
                patch("rag_search.refresh_knowledge_cache", new=refresh):
            result = await knowledge_sync.sync_brand("cfc")

        self.assertTrue(result["complete"])
        self.assertTrue(result["snapshot_validated"])
        self.assertTrue(result["vector_rebuilt"])
        self.assertTrue(result["hot_cache_refreshed"])
        self.assertTrue(result["source_snapshot_hash"].startswith("sha256:"))
        self.assertEqual(result["errors"], 0)
        self.assertEqual(len(fake.hsets), 1)
        refresh.assert_awaited_once_with("cfc", strict=True)
        self.assertTrue(fake.closed)
        status = knowledge_sync.get_sync_runtime_status("cfc")["brands"]["cfc"]
        self.assertTrue(status["complete"])
        self.assertEqual(status["source_snapshot_hash"], result["source_snapshot_hash"])

    async def test_embedding_failure_does_not_mutate_vector_or_hot_cache(self):
        fake = FakeRedis(_snapshot(_active_item()))
        refresh = AsyncMock()
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", return_value=fake), \
                patch("knowledge_sync.get_embed_dim", return_value=3), \
                patch("knowledge_sync.embed_text", new=AsyncMock(return_value=None)), \
                patch("rag_search.refresh_knowledge_cache", new=refresh):
            with self.assertRaises(knowledge_sync.KnowledgeSyncError) as caught:
                await knowledge_sync.sync_brand("cfc")

        self.assertEqual(caught.exception.stage, "embedding")
        self.assertEqual(fake.hsets, [])
        self.assertEqual(fake.deletes, [])
        refresh.assert_not_awaited()
        self.assertTrue(fake.closed)

    async def test_hot_cache_failure_never_returns_success(self):
        fake = FakeRedis(_snapshot(_active_item()))
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", return_value=fake), \
                patch("knowledge_sync.get_embed_dim", return_value=3), \
                patch("knowledge_sync.embed_text", new=AsyncMock(return_value=[0.1, 0.2, 0.3])), \
                patch("knowledge_sync.vec_to_bytes", return_value=b"vec"), \
                patch("rag_search.refresh_knowledge_cache", new=AsyncMock(side_effect=RuntimeError("cache down"))):
            with self.assertRaises(knowledge_sync.KnowledgeSyncError) as caught:
                await knowledge_sync.sync_brand("cfc")

        self.assertEqual(caught.exception.stage, "hot_cache_refresh")
        self.assertTrue(caught.exception.checkpoints["vector_rebuilt"])
        self.assertFalse(caught.exception.checkpoints["hot_cache_refreshed"])
        self.assertEqual(len(fake.hsets), 1)
        self.assertTrue(fake.closed)

    async def test_no_customer_items_preserves_existing_vector(self):
        internal = {**_active_item(), "audience": "internal"}
        fake = FakeRedis(_snapshot(internal), stale_keys=[b"cfc:vec:faq:doc:old"])
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", return_value=fake), \
                patch("knowledge_sync.get_embed_dim", return_value=3):
            with self.assertRaises(knowledge_sync.KnowledgeSyncError) as caught:
                await knowledge_sync.sync_brand("cfc")

        self.assertEqual(caught.exception.reason_code, "NO_CUSTOMER_ELIGIBLE_ITEMS")
        self.assertEqual(fake.hsets, [])
        self.assertEqual(fake.deletes, [])
        self.assertEqual(fake.commands, [])

    async def test_invalid_brand_is_rejected_before_redis_connection(self):
        redis_constructor = MagicMock()
        with patch("knowledge_sync.aioredis.Redis", redis_constructor):
            with self.assertRaises(knowledge_sync.KnowledgeSyncError) as caught:
                await knowledge_sync.sync_brand("unknown")
        self.assertEqual(caught.exception.reason_code, "INVALID_BRAND")
        redis_constructor.assert_not_called()

    async def test_candidate_key_is_allowlisted_and_used_for_strict_refresh(self):
        fake = FakeRedis(_snapshot(_active_item()))
        refresh = AsyncMock(return_value={"status": "ok", "brands": {"cfc": {"source": "redis"}}})
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", return_value=fake), \
                patch("knowledge_sync.get_embed_dim", return_value=3), \
                patch("knowledge_sync.embed_text", new=AsyncMock(return_value=[0.1, 0.2, 0.3])), \
                patch("knowledge_sync.vec_to_bytes", return_value=b"vec"), \
                patch("rag_search.refresh_knowledge_cache", new=refresh):
            result = await knowledge_sync.sync_brand(
                "cfc",
                snapshot_key="cfc:kb:basic:candidate",
            )

        self.assertEqual(fake.gets, ["cfc:kb:basic:candidate"])
        self.assertEqual(result["snapshot_key"], "cfc:kb:basic:candidate")
        refresh.assert_awaited_once_with(
            "cfc",
            strict=True,
            snapshot_key="cfc:kb:basic:candidate",
        )

    async def test_arbitrary_snapshot_key_is_rejected_before_redis_connection(self):
        redis_constructor = MagicMock()
        with patch("knowledge_sync._load_settings", return_value=CFG), \
                patch("knowledge_sync.aioredis.Redis", redis_constructor):
            with self.assertRaises(knowledge_sync.KnowledgeSyncError) as caught:
                await knowledge_sync.sync_brand("cfc", snapshot_key="amis:raw:customers")
        self.assertEqual(caught.exception.reason_code, "INVALID_SNAPSHOT_KEY")
        redis_constructor.assert_not_called()


class StrictHotCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_items = copy.deepcopy(rag_search._knowledge_items)
        self.original_intents = copy.deepcopy(rag_search._intent_map)
        self.original_phrases = copy.deepcopy(rag_search._phrase_map)
        self.original_loaded = copy.deepcopy(rag_search._cache_loaded)

    def tearDown(self):
        rag_search._knowledge_items.clear()
        rag_search._knowledge_items.update(self.original_items)
        rag_search._intent_map.clear()
        rag_search._intent_map.update(self.original_intents)
        rag_search._phrase_map.clear()
        rag_search._phrase_map.update(self.original_phrases)
        rag_search._cache_loaded.clear()
        rag_search._cache_loaded.update(self.original_loaded)

    async def test_strict_refresh_filters_inactive_and_internal_items(self):
        public = _active_item("public_faq")
        inactive = {**_active_item("inactive_faq"), "active": False}
        internal = {**_active_item("internal_faq"), "audience": "internal"}
        fake = FakeRedis(_snapshot(public, inactive, internal))
        with patch("rag_search.get_redis", new=AsyncMock(return_value=fake)), \
                patch("rag_search._load_settings", return_value=CFG):
            result = await rag_search.refresh_knowledge_cache("cfc", strict=True)

        self.assertEqual(result["brands"]["cfc"]["source"], "redis")
        self.assertEqual([item["intent"] for item in rag_search._knowledge_items["cfc"]], ["public_faq"])
        self.assertEqual(set(rag_search._intent_map["cfc"]), {"public_faq"})

    async def test_admin_refresh_replaces_a_hot_cache_without_serving_old_answer(self):
        rag_search._knowledge_items["cfc"] = [{
            "intent": "public_faq", "answer": "old answer", "active": True,
            "audience": "customer", "source_id": "old:faq",
        }]
        rag_search._intent_map["cfc"] = {
            "public_faq": rag_search._knowledge_items["cfc"][0]
        }
        updated = _active_item("public_faq")
        updated["answer"] = "new approved answer"
        updated["source_id"] = "admin:approved:v2"
        fake = FakeRedis(_snapshot(updated))

        with patch("rag_search.get_redis", new=AsyncMock(return_value=fake)), \
                patch("rag_search._load_settings", return_value=CFG):
            await rag_search.refresh_knowledge_cache("cfc", strict=True)

        self.assertEqual(rag_search._intent_map["cfc"]["public_faq"]["answer"], "new approved answer")
        self.assertEqual(rag_search._intent_map["cfc"]["public_faq"]["source_id"], "admin:approved:v2")

    async def test_strict_invalid_snapshot_keeps_previous_cache(self):
        rag_search._knowledge_items["cfc"] = [{"intent": "old", "answer": "old answer"}]
        rag_search._intent_map["cfc"] = {"old": rag_search._knowledge_items["cfc"][0]}
        fake = FakeRedis(b"not-json")
        with patch("rag_search.get_redis", new=AsyncMock(return_value=fake)), \
                patch("rag_search._load_settings", return_value=CFG), \
                patch("rag_search._load_csv_fallback") as csv_fallback:
            with self.assertRaises(RuntimeError):
                await rag_search.refresh_knowledge_cache("cfc", strict=True)

        self.assertEqual(list(rag_search._intent_map["cfc"]), ["old"])
        csv_fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
