import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from evidence_trace import assess_previous_answer_challenge  # noqa: E402
from query_understanding import build_query_plan  # noqa: E402


class PhaseTwoConversationIntelligenceTests(unittest.TestCase):
    def test_query_plan_v2_keeps_legacy_primary_and_exposes_safe_secondary(self):
        plan = build_query_plan(
            raw_text="Tôi muốn mua 200kg phân bón trồng sầu riêng",
            norm_text="toi muon mua 200kg phan bon trong sau rieng",
            brand="cfc",
        )

        self.assertEqual(plan.schema_version, 2)
        self.assertEqual(plan.intent, "cfc_purchase_request")
        self.assertTrue(plan.primary_candidate_id)
        intents = [item["intent"] for item in plan.intent_candidates]
        self.assertEqual(intents[0], "cfc_purchase_request")
        self.assertIn("cfc_agronomy_review_request", intents)
        self.assertEqual(plan.context_action, "continue")
        for candidate in plan.intent_candidates:
            self.assertNotIn("answer", candidate)
            self.assertNotIn("source_id", candidate)

    def test_sales_request_without_quantity_beats_agronomy_fallback(self):
        plan = build_query_plan(
            raw_text="Mình ở Hậu Giang, cần nhập phân, nhờ add tư vấn.",
            norm_text="minh o hau giang can nhap phan nho add tu van",
            brand="cfc",
        )

        self.assertEqual(plan.intent, "cfc_purchase_request")
        self.assertEqual(plan.constraints.get("location"), "hau giang")

    def test_technical_fertilizer_question_stays_agronomy_without_purchase_signal(self):
        plan = build_query_plan(
            raw_text="Sầu riêng bị rụng trái, nên bón phân thế nào?",
            norm_text="sau rieng bi rung trai nen bon phan the nao",
            brand="cfc",
        )

        self.assertEqual(plan.intent, "cfc_agronomy_review_request")

    def test_protected_candidate_wins_attribute_candidate(self):
        plan = build_query_plan(
            raw_text="Tra cứu đơn DH-2026-889 và báo giá giúp",
            norm_text="tra cuu don dh 2026 889 va bao gia giup",
            brand="cfc",
        )
        primary = next(item for item in plan.intent_candidates if item["candidate_id"] == plan.primary_candidate_id)
        self.assertEqual(primary["intent"], "cfc_order_status_request")
        self.assertEqual(primary["risk"], "high")

    def test_schema4_state_migrates_lazily_and_resume_does_not_copy_slots(self):
        state = chat_pipeline._load_conversation_state({
            "conversation_state": {
                "schema_version": 4,
                "active_goal": {"name": "purchase_intake", "stage": "collecting_slots"},
                "confirmed_slots": {"phone": "0901000000", "crop": "sầu riêng"},
            }
        }, "cfc")
        self.assertEqual(state["schema_version"], 5)
        self.assertEqual(len(state["goal_frames"]), 1)

        chat_pipeline._update_goal_frames(
            state, brand="cfc", intent="cfc_order_status_request",
            lead_stage="collecting_slots", user_message="tra cứu đơn DH-2026-889",
            local_slots={"order_id": "DH-2026-889", "phone": "0901000000"},
        )
        purchase = next(frame for frame in state["goal_frames"] if frame["name"] == "purchase_intake")
        order = next(frame for frame in state["goal_frames"] if frame["name"] == "order_tracking")
        self.assertEqual(purchase["status"], "paused")
        self.assertEqual(order["slots"], {"order_id": "DH-2026-889"})
        self.assertNotIn("crop", order["slots"])

        chat_pipeline._update_goal_frames(
            state, brand="cfc", intent="unknown", lead_stage="collecting_slots",
            user_message="quay lại mua hàng", local_slots={},
        )
        self.assertEqual(state["active_goal"]["name"], "purchase_intake")
        purchase = next(frame for frame in state["goal_frames"] if frame["name"] == "purchase_intake")
        self.assertEqual(purchase["status"], "active")
        self.assertEqual(state["confirmed_slots"].get("crop"), "sầu riêng")
        self.assertNotIn("order_id", state["confirmed_slots"])

    def test_last_answer_reference_is_same_session_metadata_only(self):
        state = chat_pipeline._default_conversation_state("cfc")
        state["last_answer_reference"] = {
            "answer_id": "ans:test", "claim_ids": ["claim:test"], "source_types": ["faq"],
        }
        resolved = chat_pipeline._resolve_reference(
            "Dữ liệu vừa nói đó", "du lieu vua noi do", state,
        )
        self.assertTrue(resolved["resolved"])
        self.assertEqual(resolved["reference_type"], "last_answer")
        self.assertEqual(resolved["answer_id"], "ans:test")

    def test_expired_tool_result_cannot_be_referenced_again(self):
        result = {
            "tool": "sales_location_search",
            "expires_at": "2000-01-01T00:00:00+00:00",
            "items": [{"entity_id": "dealer-1"}],
        }
        self.assertEqual(
            chat_pipeline.select_tool_result_items(result, {"reference": {}}, "đại lý đó"),
            [],
        )

    def test_source_challenge_reads_ledger_and_marks_stale_or_blocked(self):
        verified = assess_previous_answer_challenge({
            "answer_id": "ans:verified",
            "claims": [{"claim_id": "claim:1", "status": "verified"}],
            "evidence": [{"source_type": "faq", "allowed_audience": "public"}],
        })
        blocked = assess_previous_answer_challenge({
            "answer_id": "ans:blocked",
            "claims": [{"claim_id": "claim:2", "status": "blocked"}],
            "evidence": [],
        })
        stale = assess_previous_answer_challenge({
            "answer_id": "ans:stale",
            "claims": [{"claim_id": "claim:3", "status": "verified"}],
            "evidence": [{"source_type": "catalog", "allowed_audience": "public", "expires_at": "2000-01-01T00:00:00+00:00"}],
        })
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(stale["status"], "stale")

    def test_source_challenge_recognizes_customer_wording_not_only_formal_phrase(self):
        for text in (
            "thật ko, lấy từ đâu ra?",
            "thực không, nguồn gì vậy?",
            "Thông tin này lấy từ đâu?",
            "Nội dung ở trên tham khảo từ đâu?",
        ):
            with self.subTest(text=text):
                self.assertTrue(chat_pipeline._detect_source_challenge(chat_pipeline._normalize_vn(text)))

    def test_official_website_question_is_not_misclassified_as_source_challenge(self):
        for text in ("CFC có website chính thức không?", "cho xin link website chính thức"):
            with self.subTest(text=text):
                self.assertFalse(chat_pipeline._detect_source_challenge(chat_pipeline._normalize_vn(text)))


class PhaseTwoSourceChallengeIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_uses_verified_ledger_before_legacy_source_string(self):
        sender = "phase2-ledger"
        key = f"cfc:session:messenger:{sender}"
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_session_cache[key] = {
            "last_user_message": "Website chính thức?",
            "last_bot_reply": "Website đã được xác minh.",
            "last_intent": "cfc_company_website",
            "conversation_state": chat_pipeline._default_conversation_state("cfc"),
            "last_trace": {
                "source_id": "cfc_faq_split_v1",
                "answer_trace": {
                    "answer_id": "ans:previous",
                    "claims": [{"claim_id": "claim:previous", "status": "verified"}],
                    "evidence": [{"source_type": "faq", "allowed_audience": "public"}],
                },
            },
        }

        class ReadOnlyRedis:
            async def get(self, _key):
                return None

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=ReadOnlyRedis())):
            response = await chat_pipeline._process_chat_pipeline_once(
                chat_pipeline.ChatPipelineRequest(
                    brand="cfc", sender_id=sender,
                    text="Thật ko, lấy từ đâu ra?",
                )
            )

        self.assertEqual(response.intent, "source_challenge_safe_fallback")
        self.assertIn("mục kiến thức/FAQ", response.answer)
        trace = chat_pipeline._local_session_cache[key]["last_trace"]
        self.assertEqual(trace["source_challenge"]["previous_answer_id"], "ans:previous")
        self.assertEqual(trace["source_challenge"]["outcome"], "CLAIM_VERIFIED_ACKNOWLEDGED")

    async def test_website_faq_does_not_call_ai_planners(self):
        sender = "phase2-website-fast"

        class ReadOnlyRedis:
            async def get(self, _key):
                return None

        async def faq(brand, intent):
            return {
                "intent": intent,
                "answer": "Dạ website chính thức của CFC Cò Bay là https://cfccobay.com nha bạn.",
                "source_id": "test:cfc_company_website",
            }

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=ReadOnlyRedis())), \
             patch("chat_pipeline.get_faq_by_intent", new=AsyncMock(side_effect=faq)), \
             patch("chat_pipeline._llm_nlu_config", return_value=("assist", 0.3, 0.72)), \
             patch("cfc_semantic_planner.plan_cfc_intents", new=AsyncMock(side_effect=AssertionError("planner must be skipped"))), \
             patch("chat_pipeline._async_save_profile_and_notify", new=AsyncMock()):
            response = await chat_pipeline._process_chat_pipeline_once(
                chat_pipeline.ChatPipelineRequest(
                    brand="cfc", sender_id=sender,
                    text="CFC có website chính thức không?",
                )
            )

        self.assertEqual(response.intent, "cfc_company_website")
        self.assertIn("cfccobay.com", response.answer)


if __name__ == "__main__":
    unittest.main()
