import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from chat_pipeline import ChatPipelineRequest, process_chat_pipeline  # noqa: E402


class FakeRedis:
    async def get(self, key):
        return None


class MutableFakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, key):
        self.values.pop(key, None)

    async def eval(self, _script, _numkeys, key, token):
        if self.values.get(key) == token:
            self.values.pop(key, None)
            return 1
        return 0


class HandoffFlowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()

    async def test_human_request_pauses_following_bot_replies(self):
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline.notify_admin_unanswered", new=AsyncMock()), \
                patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)):
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="handoff-user",
                text="Cho mình gặp nhân viên",
            ))
            second = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="handoff-user",
                text="Mình cần xử lý đơn hàng",
            ))

        self.assertEqual(first.intent, "human_handoff_requested")
        self.assertFalse(first.suppress_send)
        self.assertEqual(second.intent, "human_handoff_active")
        self.assertTrue(second.suppress_send)
        state = chat_pipeline._local_session_cache[
            "zeo:session:messenger:handoff-user"
        ]["conversation_state"]
        self.assertEqual(state["takeover_state"]["status"], "pending")
        self.assertEqual(state["takeover_state"]["reason"], "human_handoff_requested")

    async def test_claimed_human_conversation_stays_silent(self):
        key = "cfc:session:messenger:claimed-user"
        state = chat_pipeline._default_conversation_state("cfc")
        state["takeover_state"] = {
            "status": "human", "owner": "admin-7", "reason": "admin_claimed",
        }
        chat_pipeline._local_session_cache[key] = {"conversation_state": state}

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc", sender_id="claimed-user", text="Mình gửi thêm hình sau nha",
            ))

        self.assertEqual(result.intent, "human_handoff_active")
        self.assertTrue(result.suppress_send)

    async def test_admin_can_claim_and_close_takeover_state(self):
        redis = MutableFakeRedis()
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis)):
            claimed = await chat_pipeline.set_conversation_takeover_state(
                brand="cfc", sender_id="admin-control-user", status="human",
                admin_id="admin-7", reason="picked_up_from_inbox",
            )
            closed = await chat_pipeline.set_conversation_takeover_state(
                brand="cfc", sender_id="admin-control-user", status="closed",
                admin_id="admin-7", reason="resolved",
            )

        self.assertEqual(claimed["status"], "human")
        self.assertEqual(claimed["owner"], "admin-7")
        self.assertEqual(closed["status"], "closed")
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:admin-control-user"
        ]["conversation_state"]
        self.assertEqual(state["takeover_state"]["reason"], "resolved")

    async def test_cfc_sales_request_then_phone_keeps_purchase_goal(self):
        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline._async_save_profile_and_notify", new=AsyncMock()), \
                patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)):
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc", sender_id="cfc-sales-user",
                text="Mình ở Hậu Giang, cần nhập phân, nhờ add tư vấn.",
            ))
            second = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc", sender_id="cfc-sales-user", text="0783456199",
            ))

        self.assertEqual(first.intent, "cfc_purchase_request")
        self.assertEqual(second.intent, "cfc_purchase_request")
        self.assertNotIn("Khuyến nông", second.answer)
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:cfc-sales-user"
        ]["conversation_state"]
        self.assertEqual(state["active_goal"]["name"], "purchase_intake")

    async def test_escalated_damage_does_not_promise_automatic_refund(self):
        async def faq(brand, intent):
            return {"source_id": "policy-source", "answer": "CSKH kiểm tra điều kiện đổi trả."}

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline.get_faq_by_intent", side_effect=faq), \
                patch("chat_pipeline.notify_urgent_complaint", new=AsyncMock()), \
                patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="damage-user",
                text="Đơn giao bị bể nắp chảy nước hết",
            ))

        self.assertEqual(result.intent, "urgent_damage_complaint")
        self.assertNotIn("cam kết hỗ trợ đổi mới 100%", result.answer)
        trace = chat_pipeline._local_session_cache["zeo:session:messenger:damage-user"]["last_trace"]
        self.assertEqual(trace["source_id"], "policy-source")
        self.assertEqual(trace["grounding"]["status"], "grounded")


if __name__ == "__main__":
    unittest.main()
