import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import nlu_shadow  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.expirations = {}

    async def get(self, key):
        return self.values.get(key)

    async def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    async def ltrim(self, key, start, end):
        values = self.lists.get(key, [])
        self.lists[key] = values[start:] if start < 0 else values[start:end + 1]

    async def expire(self, key, seconds):
        self.expirations[key] = seconds


class NluShadowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await nlu_shadow.drain_nlu_shadow_tasks()

    async def test_shadow_observation_is_redacted_bounded_and_compared(self):
        redis_client = FakeRedis()
        session_key = "zeo:session:messenger:sender-1"
        query = "Giá nước giặt, gọi tôi 0908776655"
        redis_client.values[session_key] = json.dumps({
            "last_user_message": query,
            "last_intent": "specific_product_pricing",
        })
        prediction = {
            "intent": "specific_price",
            "confidence": 0.91,
            "reason": "Khach de lai 0908776655 de hoi gia",
            "provider": "ollama",
            "model": "fake",
        }

        with patch("nlu_shadow.plan_chat_intent_with_ai", new=AsyncMock(return_value=prediction)) as planner, \
                patch("nlu_shadow.get_redis", new=AsyncMock(return_value=redis_client)):
            observation = await nlu_shadow.collect_nlu_shadow_observation(
                brand="zeo",
                sender_id="sender-1",
                message_id="mid-1",
                raw_text=query,
                normalized_text="gia nuoc giat goi toi 0908776655",
                conversation_summary="previous_intent=product_information_query",
                deterministic_plan={
                    "intent": "product_price_query",
                    "intent_confidence": 0.86,
                    "attributes": ["price"],
                    "needs_context": False,
                    "needs_product_tool": True,
                },
                confidence_threshold=0.72,
                timeout=5.0,
                max_observations=500,
                retention_seconds=604800,
            )

        planner.assert_awaited_once()
        self.assertNotIn("query", observation)
        self.assertNotIn("0908776655", str(observation))
        self.assertNotIn("sender-1", observation["sender_hash"])
        self.assertEqual(observation["actual_route"], "specific_product_pricing")
        self.assertEqual(observation["actual_status"], "captured")
        self.assertEqual(observation["semantic_proposal"]["intent"], "specific_price")
        self.assertTrue(observation["agreement"])
        self.assertTrue(observation["meets_threshold"])
        self.assertEqual(len(redis_client.lists["zeo:shadow:v2:events"]), 1)
        self.assertEqual(redis_client.expirations["zeo:shadow:v2:events"], 604800)

    async def test_scheduler_is_non_blocking_and_bounded(self):
        gate = AsyncMock()
        gate.side_effect = lambda **kwargs: None
        with patch("nlu_shadow._shadow_config", return_value={
                "timeout": 5.0,
                "max_pending": 1,
                "max_observations": 100,
                "retention_seconds": 3600,
                "sample_rate": 1.0,
            }), patch("nlu_shadow.collect_nlu_shadow_observation", gate):
            status = nlu_shadow.schedule_nlu_shadow(
                brand="zeo",
                sender_id="sender-2",
                message_id="mid-2",
                raw_text="san pham nao mac nhat",
                normalized_text="san pham nao mac nhat",
                conversation_summary="",
                deterministic_plan={},
                confidence_threshold=0.72,
            )
            self.assertEqual(status, "scheduled")
            second_status = nlu_shadow.schedule_nlu_shadow(
                brand="zeo",
                sender_id="sender-3",
                message_id="mid-3",
                raw_text="cho minh xin link san pham",
                normalized_text="cho minh xin link san pham",
                conversation_summary="",
                deterministic_plan={},
                confidence_threshold=0.72,
            )
            self.assertEqual(second_status, "queue_full")
            await nlu_shadow.drain_nlu_shadow_tasks()

        gate.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
