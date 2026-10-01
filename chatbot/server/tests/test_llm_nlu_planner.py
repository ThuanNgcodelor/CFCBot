import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
import ai_engine  # noqa: E402
from chat_pipeline import ChatPipelineRequest, process_chat_pipeline  # noqa: E402
from shopee_matcher import match_price_extreme  # noqa: E402


class FakeRedis:
    async def get(self, key):
        return None


class LlmNluPlannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_ai_planner_returns_runtime_provider_and_model_without_name_error(self):
        raw = '{"intent":"product_search","confidence":0.91,"sort":"","need_type":"","category":"","product":"nước giặt","reference":false,"reason":"test"}'
        with patch(
            "ai_engine.generate_ai_text",
            new=AsyncMock(return_value={"text": raw, "provider": "groq", "model": "test-model"}),
        ):
            plan = await ai_engine.plan_chat_intent_with_ai(
                user_query="Zeo có nước giặt không?",
                brand="zeo",
            )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["provider"], "groq")
        self.assertEqual(plan["model"], "test-model")

    async def test_ollama_plan_can_route_unseen_highest_price_wording_to_catalog_tool(self):
        catalog = [
            {
                "item_id": "LOW",
                "name": "Nước xả vải ZeO dùng thử",
                "brand": "ZeO",
                "category": "Nước xả vải",
                "price": 17_100,
                "in_stock": True,
                "link_shopee": "https://shopee.vn/low",
            },
            {
                "item_id": "MAX",
                "name": "Thùng nước giặt Pano Active 6 túi",
                "brand": "PANO",
                "category": "Nước giặt",
                "price": 681_812,
                "in_stock": True,
                "link_shopee": "https://shopee.vn/max",
            },
        ]

        async def fake_planner(**kwargs):
            return {
                "intent": "price_extreme",
                "confidence": 0.94,
                "sort": "highest",
                "need_type": "",
                "category": "",
                "product": "",
                "reference": False,
                "reason": "khách hỏi sản phẩm giá cao nhất bằng cách nói tự nhiên",
                "provider": "ollama",
                "model": "fake",
            }

        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline._llm_nlu_config", return_value=("assist", 0.3, 0.72)), \
                patch("chat_pipeline.plan_chat_intent_with_ai", side_effect=fake_planner), \
                patch("shopee_matcher.load_shopee_catalog", return_value=catalog), \
                patch("chat_pipeline._async_save_session", new=AsyncMock()):
            res = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="test-llm-nlu",
                text="shop ơi món nào giá chát nhất vậy",
            ))

        self.assertEqual(res.intent, "shopee_price_extreme")
        self.assertIn("681.812đ", res.answer)
        self.assertIn("Thùng nước giặt Pano Active", res.answer)

    def test_forced_price_extreme_mode_still_uses_catalog_sorting(self):
        catalog = [
            {"item_id": "LOW", "name": "Giá thấp", "brand": "ZeO", "category": "Nước xả vải", "price": 10_000, "in_stock": True},
            {"item_id": "MAX", "name": "Giá cao", "brand": "PANO", "category": "Nước giặt", "price": 600_000, "in_stock": True},
        ]
        with patch("shopee_matcher.load_shopee_catalog", return_value=catalog):
            result = match_price_extreme("món nào giá chát vậy", brand="zeo", mode="highest")

        self.assertEqual(result["matched_product"]["item_id"], "MAX")


if __name__ == "__main__":
    unittest.main()
