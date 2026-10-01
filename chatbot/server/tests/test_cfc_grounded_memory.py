import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from chat_pipeline import (
    ChatPipelineRequest,
    _extract_cfc_confirmed_slots,
    _extract_phone_and_area,
    _normalize_vn,
    process_chat_pipeline,
)  # noqa: E402


class FakeRedis:
    def __init__(self, values=None):
        self.values = values or {}

    async def get(self, key):
        return self.values.get(key)


FAQS = {
    "cfc_dealer_location_request": (
        "Dạ bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành cụ thể. "
        "Admin sẽ chuyển thông tin để nhân viên khu vực hỗ trợ ạ."
    ),
    "cfc_dosage_usage_review": (
        "Dạ phần liều lượng, cách bón hoặc phối trộn cần kỹ sư nông nghiệp kiểm tra "
        "theo cây trồng, giai đoạn và khu vực canh tác."
    ),
    "cfc_price_unverified": (
        "Dạ bảng giá phụ thuộc dòng sản phẩm, quy cách và khu vực phân phối."
    ),
    "cfc_agronomy_young_fruit_sizing": (
        "Dạ khi trái non đã định hình, dùng NPK Cò Bay 20-20-15 TE hoặc "
        "15-15-15/16-16-16 TE, kết hợp Canxi, Magie và chia nhỏ 10-12 ngày/lần."
    ),
    "cfc_agronomy_flowering_fruit_retention": (
        "Dạ giai đoạn hoa cần lưu ý Canxi, Bo, Kẽm và hạn chế Đạm cao."
    ),
    "cfc_company_website": "Dạ website chính thức của CFC Cò Bay là https://cfccobay.com nha bạn.",
}


async def fake_faq(brand, intent):
    answer = FAQS.get(intent, "")
    return {"intent": intent, "answer": answer, "source_id": f"test:{intent}"} if answer else {}


class CfcGroundedMemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()

    def _patches(self, redis_client=None):
        return (
            patch("chat_pipeline.get_redis", new=AsyncMock(return_value=redis_client or FakeRedis())),
            patch("chat_pipeline.get_faq_by_intent", side_effect=fake_faq),
            patch("chat_pipeline._async_save_profile_and_notify", new=AsyncMock()),
            patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)),
        )

    def test_area_extraction_keeps_only_location_phrase(self):
        cases = {
            "Tôi ở gần chợ Ô Môn, muốn mua 10 bao phân NPK": "chợ Ô Môn",
            "Khu vực xã Định Môn, Thới Lai có đại lý nào giao tận nhà không shop?": "xã Định Môn, Thới Lai",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                _, area = _extract_phone_and_area(text, _normalize_vn(text))
                self.assertEqual(area, expected)

    def test_agronomy_sentence_does_not_become_area(self):
        slots = _extract_cfc_confirmed_slots(
            "Sầu riêng ở giai đoạn nuôi trái non bị rụng hạt chuỗi thì nên bón công thức NPK nào?"
        )
        self.assertEqual(slots.get("crop"), "sầu riêng")
        self.assertEqual(slots.get("crop_stage"), "nuôi trái non")
        self.assertEqual(slots.get("symptom"), "rụng hạt chuỗi")
        self.assertNotIn("area", slots)

    def test_large_order_cooperative_does_not_become_kumquat_crop(self):
        slots = _extract_cfc_confirmed_slots(
            "Tôi muốn đặt 30 tấn phân bón cho hợp tác xã, cần gặp giám đốc kinh doanh"
        )
        self.assertEqual(slots.get("quantity"), "30 tấn")
        self.assertNotIn("crop", slots)

    def test_cfc_workflow_forwards_messenger_location_contract(self):
        workflow = (
            SERVER_DIR.parents[1]
            / "workflows"
            / "local-n8n"
            / "cfc_cobay_chatbot.workflow.ts"
        ).read_text(encoding="utf-8")
        for expected in (
            "payload?.coordinates",
            "input_kind: $json.inputKind",
            "latitude: $json.latitude",
            "longitude: $json.longitude",
        ):
            self.assertIn(expected, workflow)

    def test_customer_boundaries_do_not_expose_internal_integration_terms(self):
        large_order = chat_pipeline._format_b2b_large_order_reply(
            "Tôi cần mua 30 tấn NPK cho hợp tác xã",
        )
        order_status, _ = chat_pipeline._build_cfc_capability_boundary(
            "cfc_order_status_unavailable",
            {"order_id": "DH-2026-889"},
        )

        self.assertNotIn("B2B", large_order)
        self.assertNotIn("chatbot", large_order.lower())
        self.assertNotIn("dữ liệu thương mại", large_order.lower())
        self.assertIn("bộ phận phụ trách", large_order.lower())
        self.assertNotIn("chưa kết nối", order_status.lower())
        self.assertIn("mã đơn", order_status.lower())
        self.assertNotIn("cuộc chat này", order_status.lower())

    async def test_inventory_goal_resumes_after_phone_only_turn(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="inventory-resume",
                text="Sản phẩm NPK 16-16-8 TE bao 50kg trong kho còn nhiều không? Lấy 5 tấn có liền không?",
            ))
            second = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="inventory-resume",
                text="0979176415",
            ))

        self.assertEqual(first.intent, "cfc_inventory_unavailable")
        self.assertIn("số lượng còn hàng và lịch giao", first.answer)
        self.assertEqual(second.intent, "cfc_inventory_unavailable")
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:inventory-resume"
        ]["conversation_state"]
        self.assertEqual(state["active_goal"]["name"], "inventory_check")
        self.assertEqual(state["confirmed_slots"]["formula"], "16-16-8 TE")
        self.assertEqual(state["confirmed_slots"]["quantity"], "5 tấn")
        self.assertEqual(state["confirmed_slots"]["phone"], "0979176415")
        self.assertEqual(state["pending_slots"], ["area"])

    async def test_explicit_purchase_keeps_crop_and_quantity_in_active_goal(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="purchase-intake",
                text="Tôi muốn mua 200kg phân bón trồng sầu riêng",
            ))

        self.assertEqual(result.intent, "cfc_purchase_request")
        self.assertIn("200kg", result.answer)
        self.assertIn("sầu riêng", result.answer)
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:purchase-intake"
        ]["conversation_state"]
        self.assertEqual(state["active_goal"]["name"], "purchase_intake")
        self.assertEqual(state["confirmed_slots"]["quantity"], "200kg")
        self.assertEqual(state["confirmed_slots"]["crop"], "sầu riêng")
        self.assertIn("product", state["pending_slots"])
        self.assertIn("phone", state["pending_slots"])

    async def test_purchase_clarification_reuses_active_goal(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="purchase-clarification",
                text="Tôi muốn mua 200kg phân bón trồng sầu riêng",
            ))
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="purchase-clarification",
                text="Là sao? Chưa hiểu",
            ))

        self.assertEqual(result.intent, "cfc_clarification_request")
        self.assertIn("200kg", result.answer)
        self.assertIn("mua", result.answer.lower())
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:purchase-clarification"
        ]["conversation_state"]
        self.assertEqual(state["active_goal"]["name"], "purchase_intake")
        self.assertEqual(state["confirmed_slots"]["quantity"], "200kg")

    async def test_phone_with_loyalty_question_looks_up_exact_phone(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch(
                    "chat_pipeline.lookup_cached_loyalty_info",
                    new=AsyncMock(return_value={
                        "outcome": "not_found",
                        "source_id": "amis:internal:loyalty-warm",
                    }),
                ):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="loyalty-intent",
                text="Số điện thoại của mình là 0979176415, kiểm tra xem mình có tích điểm hay chiết khấu gì chưa?",
            ))

        self.assertEqual(result.intent, "cfc_loyalty_lookup_request")
        self.assertNotEqual(result.intent, "contact_phone_provided")
        self.assertIn("chưa tìm thấy hồ sơ", result.answer.lower())
        self.assertNotIn("đã có điểm", result.answer.lower())
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:loyalty-intent"
        ]["conversation_state"]
        self.assertEqual(state["active_goal"]["name"], "loyalty_lookup")
        self.assertEqual(state["confirmed_slots"]["phone"], "0979176415")

    async def test_order_status_uses_warm_cache_when_code_and_phone_match(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        cached_lookup = AsyncMock(return_value={
            "outcome": "found",
            "order_code": "DH-2026-889",
            "status": "Đang giao hàng",
            "delivery_status": "Đã giao hàng",
            "sale_order_date": "2026-08-28",
            "deadline_date": "2026-08-30",
            "order_updated_at": "2026-08-29T07:45:00+00:00",
            "synced_at": "2026-08-29T08:00:00+00:00",
            "source_id": "amis:internal:order-warm",
        })
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.lookup_cached_order_status", new=cached_lookup):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="order-warm-match",
                text="Tra cứu đơn DH-2026-889, số điện thoại đặt hàng 0901234567",
            ))

        cached_lookup.assert_awaited_once()
        self.assertEqual(result.intent, "cfc_order_status_request")
        self.assertIn("DH-2026-889", result.answer)
        self.assertIn("Đang giao hàng", result.answer)
        self.assertIn("Tình trạng giao hàng: Đã giao hàng", result.answer)
        self.assertIn("Ngày đặt đơn: 28/08/2026", result.answer)
        self.assertIn("Hạn giao hàng trên đơn: 30/08/2026", result.answer)
        self.assertNotIn("2026-08-29T", result.answer)
        self.assertNotIn("chưa kết nối", result.answer.lower())
        self.assertNotIn("CRM", result.answer)
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:order-warm-match"
        ]["last_trace"]
        self.assertEqual(trace["source_id"], "amis:internal:order-warm")

    async def test_explicit_order_lookup_skips_ollama_semantic_and_conversation_planners(self):
        redis_patch, faq_patch, profile_patch, _ = self._patches()
        cached_lookup = AsyncMock(return_value={
            "outcome": "found",
            "order_code": "00005065",
            "shop_name": "Cửa hàng Minh An",
            "status": "Đã thực hiện",
            "delivery_status": "Đã giao hàng",
            "sale_order_date": "2026-08-28",
            "deadline_date": "2026-08-30",
            "source_id": "amis:internal:order-warm",
        })
        semantic_planner = AsyncMock(return_value=[])
        conversation_planner = AsyncMock(return_value=None)
        sender_id = "order-fast-path"
        session_key = f"cfc:session:messenger:{sender_id}"
        state = chat_pipeline._default_conversation_state("cfc")
        state["recent_turns"] = [{"user": "Tôi cần hỗ trợ", "bot": "Bạn gửi mã đơn nhé."}]
        chat_pipeline._local_session_cache[session_key] = {
            "conversation_state": state,
            "last_intent": "general_faq",
        }
        with redis_patch, faq_patch, profile_patch, \
                patch("chat_pipeline._llm_nlu_config", return_value=("assist", 1.6, 0.72)), \
                patch("chat_pipeline.load_orchestrator_config", return_value={
                    "mode": "assist", "min_confidence": 0.85, "history_limit": 6, "timeout_seconds": 6.0,
                }), \
                patch("cfc_semantic_planner.plan_cfc_intents", new=semantic_planner), \
                patch("chat_pipeline.plan_conversation_turn_with_ai", new=conversation_planner), \
                patch("chat_pipeline.lookup_cached_order_status", new=cached_lookup):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Tra cứu đơn 00005065 số điện thoại 0976000085",
            ))

        self.assertEqual(result.intent, "cfc_order_status_request")
        semantic_planner.assert_not_awaited()
        conversation_planner.assert_not_awaited()
        self.assertIn("Tình trạng giao hàng: Đã giao hàng", result.answer)

    async def test_order_status_preserves_plain_numeric_order_code_for_warm_lookup(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        cached_lookup = AsyncMock(return_value={
            "outcome": "found",
            "order_code": "00005065",
            "status": "Đang xử lý",
            "order_updated_at": "2026-08-29T07:45:00+00:00",
            "synced_at": "2026-08-29T08:00:00+00:00",
            "source_id": "amis:internal:order-warm",
        })
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.lookup_cached_order_status", new=cached_lookup):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="order-numeric-match",
                text="Tra cứu giúp tôi đơn 00005065 số điện thoại 0976000085",
            ))

        cached_lookup.assert_awaited_once()
        self.assertEqual(cached_lookup.await_args.kwargs["order_code"], "00005065")
        self.assertEqual(cached_lookup.await_args.kwargs["phone"], "0976000085")
        self.assertEqual(result.intent, "cfc_order_status_request")
        self.assertIn("Đang xử lý", result.answer)

    async def test_order_status_reports_no_match_without_disclosing_any_order(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        cached_lookup = AsyncMock(return_value={
            "outcome": "not_found",
            "synced_at": "2026-08-29T08:00:00+00:00",
            "source_id": "amis:internal:order-warm",
        })
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.lookup_cached_order_status", new=cached_lookup):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="order-warm-no-match",
                text="Tra cứu đơn DH-404, số điện thoại đặt hàng 0901234567",
            ))

        self.assertEqual(result.intent, "cfc_order_status_request")
        self.assertIn("chưa tìm thấy đơn khớp", result.answer.lower())
        self.assertNotIn("trạng thái hiện ghi nhận", result.answer.lower())
        self.assertNotIn("CRM", result.answer)

    async def test_agronomy_reply_uses_grounded_handbook_direction_without_inventing_kg_dose(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        agronomy_search = AsyncMock(return_value={
            "confidence": "high",
            "score": 0.91,
            "results": [
                {
                    "intent": "cfc_agronomy_young_fruit_sizing",
                    "answer": FAQS["cfc_agronomy_young_fruit_sizing"],
                    "category": "agronomy",
                    "audience": "customer",
                    "risk_level": "medium",
                    "source_id": "test:cfc_agronomy_young_fruit_sizing",
                    "score": 0.91,
                },
                {
                    "intent": "cfc_agronomy_flowering_fruit_retention",
                    "answer": FAQS["cfc_agronomy_flowering_fruit_retention"],
                    "category": "agronomy",
                    "audience": "customer",
                    "risk_level": "medium",
                    "source_id": "test:cfc_agronomy_flowering_fruit_retention",
                    "question_examples": "bón gì chống rụng hoa sinh lý; chống rụng trái non",
                    "learning_tags": "flowering|fruit_drop_prevention",
                    "score": 0.84,
                },
            ],
        })
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=agronomy_search), \
                patch("chat_pipeline.synthesize_cskh_answer", new=AsyncMock(return_value=None)):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="agronomy-intake",
                text="Sầu riêng giai đoạn nuôi trái non bị rụng hạt chuỗi thì nên bón công thức NPK nào và liều lượng sao?",
            ))

        self.assertEqual(result.intent, "cfc_dosage_usage_review")
        for expected in (
            "sầu riêng",
            "nuôi trái non",
            "rụng hạt chuỗi",
            "20-20-15 TE",
            "Canxi, Bo, Kẽm",
            "10-12 ngày/lần",
            "chưa có mức kg/gốc",
        ):
            self.assertIn(expected, result.answer)
        self.assertNotIn("chatbot", result.answer.lower())
        self.assertNotRegex(result.answer, r"\b\d+(?:[.,]\d+)?\s*kg/gốc\b")
        self.assertLess(result.latency_ms, 500)
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:agronomy-intake"
        ]["last_trace"]
        self.assertEqual(trace["source_id"], "test:cfc_agronomy_young_fruit_sizing")
        self.assertEqual(
            trace["customer_fact_generation_mode"],
            "grounded_faq_composition_fallback",
        )
        self.assertEqual(trace["agronomy_evidence_count"], 2)
        agronomy_search.assert_awaited_once()

    async def test_agronomy_grounded_facts_can_be_rewritten_without_changing_source(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        agronomy_search = AsyncMock(return_value={
            "confidence": "high",
            "score": 0.9,
            "results": [{
                "intent": "cfc_agronomy_young_fruit_sizing",
                "answer": FAQS["cfc_agronomy_young_fruit_sizing"],
                "category": "agronomy",
                "audience": "customer",
                "risk_level": "medium",
                "source_id": "test:cfc_agronomy_young_fruit_sizing",
                "score": 0.9,
            }],
        })
        natural_answer = (
            "Dạ với sầu riêng đang nuôi trái non, mình nên cân đối dinh dưỡng theo "
            "hướng dẫn đã đối chiếu; phần kg/gốc cần kỹ sư kiểm tra sát vườn ạ."
        )
        synthesizer = AsyncMock(return_value=natural_answer)
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=agronomy_search), \
                patch("chat_pipeline.synthesize_cskh_answer", new=synthesizer):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="agronomy-grounded-rewrite",
                text="Sầu riêng nuôi trái non bị rụng hạt chuỗi nên bón gì?",
            ))

        self.assertEqual(result.answer, natural_answer)
        synthesizer.assert_awaited_once()
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:agronomy-grounded-rewrite"
        ]["last_trace"]
        self.assertEqual(trace["source_id"], "test:cfc_agronomy_young_fruit_sizing")
        self.assertEqual(trace["customer_fact_generation_mode"], "grounded_rewrite")

    async def test_tc01_price_family_shows_catalog_then_asks_missing_slots_once(self):
        product_snapshot = {
            "items": [
                {
                    "product_name": "NPK Cò bay 20-20-15 bao 25kg",
                    "product_code": "01.INTERNAL-25",
                    "product_category": "PHÂN NPK",
                },
                {
                    "product_name": "NPK Cò bay 20-20-15 bao 50kg",
                    "product_code": "01.INTERNAL-50",
                    "product_category": "PHÂN NPK",
                },
                {
                    "product_name": "NPK Cò bay 16-16-8 bao 50kg",
                    "product_code": "01.OTHER",
                    "product_category": "PHÂN NPK",
                },
            ]
        }
        import json

        redis_client = FakeRedis({
            chat_pipeline.PRODUCT_SNAPSHOT_KEY: json.dumps(product_snapshot, ensure_ascii=False),
        })
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches(redis_client)
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="tc01-price-family",
                text="Chào em, mình muốn tìm hiểu giá phân NPK 20-20-15 để chuẩn bị bón cho vụ tới.",
            ))

        self.assertEqual(result.intent, "cfc_price_unverified")
        self.assertIn("NPK Cò bay 20-20-15 bao 25kg", result.answer)
        self.assertIn("NPK Cò bay 20-20-15 bao 50kg", result.answer)
        self.assertIn("số điện thoại", result.answer)
        self.assertIn("khu vực nhận hàng", result.answer)
        self.assertIn("loại cây trồng", result.answer)
        self.assertEqual(result.answer.count("Bạn cho mình xin"), 1)
        self.assertNotIn("01.INTERNAL", result.answer)
        self.assertNotIn("Mình đang giữ thông tin", result.answer)
        self.assertLess(result.latency_ms, 500)

    async def test_clear_tc01_and_tc12_skip_semantic_planner(self):
        product_snapshot = {
            "items": [{
                "product_name": "NPK Cò bay 20-20-15 bao 25kg",
                "product_code": "01.INTERNAL",
                "product_category": "PHÂN NPK",
            }]
        }
        import json

        redis_client = FakeRedis({
            chat_pipeline.PRODUCT_SNAPSHOT_KEY: json.dumps(product_snapshot, ensure_ascii=False),
        })
        redis_patch, faq_patch, profile_patch, _ = self._patches(redis_client)
        semantic_planner = AsyncMock(return_value=[])
        agronomy_search = AsyncMock(return_value={
            "confidence": "high",
            "score": 0.9,
            "results": [{
                "intent": "cfc_agronomy_young_fruit_sizing",
                "answer": FAQS["cfc_agronomy_young_fruit_sizing"],
                "category": "agronomy",
                "audience": "customer",
                "risk_level": "medium",
                "source_id": "test:cfc_agronomy_young_fruit_sizing",
                "score": 0.9,
            }],
        })
        with redis_patch, faq_patch, profile_patch, \
                patch("chat_pipeline._llm_nlu_config", return_value=("assist", 0.3, 0.72)), \
                patch("cfc_semantic_planner.plan_cfc_intents", new=semantic_planner), \
                patch("chat_pipeline.semantic_search", new=agronomy_search), \
                patch("chat_pipeline.synthesize_cskh_answer", new=AsyncMock(return_value=None)):
            await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="tc01-fast-route",
                text="Báo giá NPK 20-20-15 giúp mình",
            ))
            await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="tc12-fast-route",
                text="Sầu riêng nuôi trái non bị rụng hạt chuỗi, bón công thức nào?",
            ))

        semantic_planner.assert_not_awaited()
        price_trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:tc01-fast-route"
        ]["last_trace"]
        agronomy_trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:tc12-fast-route"
        ]["last_trace"]
        self.assertEqual(
            price_trace["protected_fast_path"]["reason"],
            "GROUNDED_PRICE_ROUTE_SKIPS_AI_PLANNERS",
        )
        self.assertEqual(
            agronomy_trace["protected_fast_path"]["reason"],
            "CLEAR_AGRONOMY_ROUTE_SKIPS_AI_PLANNERS",
        )

    async def test_explicit_cfc_operational_route_skips_both_ai_planners(self):
        sender_id = "explicit-cfc-fast-route"
        session_key = f"cfc:session:messenger:{sender_id}"
        state = chat_pipeline._default_conversation_state("cfc")
        state["recent_turns"] = [{"user": "Chào em", "bot": "Dạ chào bạn"}]
        chat_pipeline._local_session_cache[session_key] = {
            "last_user_message": "Chào em",
            "last_bot_reply": "Dạ chào bạn",
            "last_intent": "greeting",
            "conversation_state": state,
        }
        redis_patch, faq_patch, profile_patch, _ = self._patches()
        semantic_planner = AsyncMock(return_value=[])
        conversation_planner = AsyncMock(return_value=None)
        with redis_patch, faq_patch, profile_patch, \
                patch("chat_pipeline._llm_nlu_config", return_value=("assist", 0.3, 0.72)), \
                patch("cfc_semantic_planner.plan_cfc_intents", new=semantic_planner), \
                patch("chat_pipeline.plan_conversation_turn_with_ai", new=conversation_planner):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Phân bón bị vón cục, tôi muốn khiếu nại đổi trả ngay",
            ))

        self.assertEqual(result.intent, "cfc_product_complaint_request")
        semantic_planner.assert_not_awaited()
        conversation_planner.assert_not_awaited()
        trace = chat_pipeline._local_session_cache[session_key]["last_trace"]
        self.assertEqual(
            trace["protected_fast_path"]["reason"],
            "EXPLICIT_CFC_ROUTE_SKIPS_AI_PLANNERS",
        )

    async def test_durian_eligibility_does_not_expand_into_protocol_or_policy(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="durian-eligibility",
                text="Có phân bón cho cây sầu riêng hay không?",
            ))

        self.assertIn(result.intent, {"cfc_crop_consultation_request", "cfc_dosage_usage_review"})
        self.assertIn("sầu riêng", result.answer)
        self.assertIn("CFC có các dòng NPK và phân hữu cơ", result.answer)
        self.assertIn("kỹ sư sẽ đối chiếu", result.answer)
        self.assertNotIn("số điện thoại", result.answer.lower())
        self.assertNotRegex(result.answer, r"\b\d{1,3}\s*kg/ha\b")
        self.assertNotRegex(result.answer, r"\b\d{1,2}-\d{1,2}-\d{1,2}\b")
        self.assertNotIn("giá xuất xưởng", result.answer.lower())
        self.assertNotIn("miễn phí vận chuyển", result.answer.lower())
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:durian-eligibility"
        ]["last_trace"]
        self.assertEqual(trace["agronomy_fact"]["fact_id"], "cfc-product-family-eligibility-durian-v1")
        self.assertEqual(trace["source_id"], "cfc_reply_docx_v1")

    async def test_approved_agronomy_eligibility_skips_cfc_semantic_planner(self):
        redis_patch, faq_patch, profile_patch, _ = self._patches()
        semantic_planner = AsyncMock(return_value=[])
        with redis_patch, faq_patch, profile_patch, \
                patch("chat_pipeline._llm_nlu_config", return_value=("assist", 0.3, 0.72)), \
                patch("cfc_semantic_planner.plan_cfc_intents", new=semantic_planner):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="durian-fast-fact",
                text="Có phân bón cho cây sầu riêng hay không?",
            ))

        self.assertIn("CFC có các dòng NPK và phân hữu cơ", result.answer)
        semantic_planner.assert_not_awaited()
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:durian-fast-fact"
        ]["last_trace"]
        self.assertEqual(
            trace["protected_fast_path"]["reason"],
            "APPROVED_ELIGIBILITY_FACT_SKIPS_AI_PLANNERS",
        )

    def test_order_reply_shows_business_update_but_not_cache_sync_time(self):
        answer, reason = chat_pipeline._format_order_lookup_reply({
            "outcome": "found",
            "order_code": "00005065",
            "shop_name": "Cửa hàng Minh An",
            "status": "Đã thực hiện",
            "sale_order_date": "2026-08-26T00:00:00+07:00",
            "order_updated_at": "2026-08-28T09:03:40+07:00",
            "synced_at": "2026-08-29T09:38:23+00:00",
        })

        self.assertEqual(reason, "ORDER_CACHE_MATCHED")
        self.assertIn("Cập nhật gần nhất: 09:03 ngày 28/08/2026", answer)
        self.assertIn("Tên cửa hàng: Cửa hàng Minh An", answer)
        self.assertNotIn("đồng bộ", answer.lower())

    async def test_cfc_accented_acknowledgement_does_not_fall_back_to_general_support(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="cfc-acknowledgement",
                text="À ok",
            ))

        self.assertEqual(result.intent, "acknowledgement")
        self.assertNotIn("cần admin hỗ trợ gì", result.answer.lower())

    async def test_source_challenge_retracts_previous_ungrounded_details(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=AsyncMock(return_value={
                    "answer": "", "intent": "", "score": 0.0, "source_id": "",
                })), \
                patch("chat_pipeline.notify_admin_unanswered", new=AsyncMock()):
            await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="source-challenge",
                text="Phân này có chống chịu mặn tuyệt đối không?",
            ))
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="source-challenge",
                text="Dữ liệu đó có thật không, nguồn đâu?",
            ))

        self.assertEqual(result.intent, "source_challenge_safe_fallback")
        self.assertEqual(result.fallback_reason, "SOURCE_CHALLENGE_SAFE_FALLBACK")
        self.assertIn("không khẳng định thêm", result.answer.lower())
        self.assertNotIn("model", result.answer.lower())
        self.assertNotIn("nguồn nghiệp vụ", result.answer.lower())
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:source-challenge"
        ]["last_trace"]
        self.assertEqual(trace["source_challenge"]["outcome"], "UNVERIFIED_DETAILS_RETRACTED")

    async def test_source_challenge_only_acknowledges_safe_source_type(self):
        sender_id = "source-challenge-grounded"
        session_key = f"cfc:session:messenger:{sender_id}"
        chat_pipeline._local_session_cache[session_key] = {
            "last_user_message": "Website nào chính thức?",
            "last_bot_reply": "Website đã được ghi trong Knowledge.",
            "last_intent": "cfc_company_website",
            "lead_stage": "browsing_catalog",
            "conversation_state": chat_pipeline._default_conversation_state("cfc"),
            "last_trace": {
                "source_id": "cfc_faq_split_v1",
                "fallback_reason": "",
            },
        }
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Nguồn đâu, thông tin đó có thật không?",
            ))

        self.assertEqual(result.intent, "source_challenge_safe_fallback")
        self.assertIn("mục kiến thức/FAQ", result.answer)
        self.assertNotIn("cfc_faq_split_v1", result.answer)
        self.assertNotIn("phase 0", result.answer.lower())
        trace = chat_pipeline._local_session_cache[session_key]["last_trace"]
        self.assertEqual(trace["source_challenge"]["outcome"], "SOURCE_TYPE_ACKNOWLEDGED")

    async def test_agronomy_dosage_and_source_followups_keep_previous_context(self):
        sender_id = "agronomy-followup-chain"
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        agronomy_search = AsyncMock(return_value={
            "confidence": "high",
            "score": 0.9,
            "results": [{
                "intent": "cfc_agronomy_young_fruit_sizing",
                "answer": (
                    "Dạ với sầu riêng giai đoạn nuôi trái non, cần kiểm tra bộ rễ, "
                    "ẩm độ, thoát nước và tránh dư đạm; cân đối Kali và Canxi-Bo. "
                    "Liều lượng phải căn cứ tuổi cây, mật độ và hiện trạng vườn."
                ),
                "category": "agronomy",
                "audience": "customer",
                "risk_level": "medium",
                "source_id": "cfc_handbook_50_nha_nong_v1:young_fruit",
                "score": 0.9,
            }],
        })
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=agronomy_search), \
                patch("chat_pipeline.synthesize_cskh_answer", new=AsyncMock(return_value=None)):
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Sầu riêng nuôi trái non bị rụng hạt chuỗi thì nên bón gì?",
            ))
            dosage = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Liều bao nhiêu một gốc?",
            ))
            source = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id=sender_id,
                text="Thông tin này lấy từ đâu?",
            ))

        self.assertIn("sầu riêng", first.answer.lower())
        self.assertEqual(dosage.intent, "cfc_dosage_usage_review")
        self.assertIn("sầu riêng", dosage.answer.lower())
        self.assertIn("Lê Thanh Đạm", dosage.answer)
        self.assertIn("chưa có mức kg/gốc", dosage.answer)
        self.assertNotIn("phối trộn", dosage.answer.lower())
        self.assertNotIn("thuốc trừ sâu", dosage.answer.lower())
        self.assertGreaterEqual(agronomy_search.await_count, 2)
        followup_query = str(agronomy_search.await_args_list[1].kwargs.get("query") or "")
        self.assertIn("sầu riêng", followup_query.lower())
        self.assertIn("nuôi trái non", followup_query.lower())

        self.assertEqual(source.intent, "source_challenge_safe_fallback")
        self.assertIn("cẩm nang kỹ thuật cfc", source.answer.lower())
        self.assertNotIn("cfccobay.com", source.answer.lower())
        self.assertNotIn("mua hàng trực tuyến", source.answer.lower())

    def test_generator_source_is_blocked_before_customer_send(self):
        sender_id = "provider-source-block"
        session_key = f"cfc:session:messenger:{sender_id}"
        chat_pipeline._local_session_cache[session_key] = {
            "last_trace": {
                "source_id": "ollama:cfc_agronomy",
                "fallback_reason": "",
            },
            "conversation_state": {"recent_turns": []},
        }
        response = chat_pipeline.ChatPipelineResponse(
            answer="NPK 20-20-15, bón 200kg/ha.",
            intent="cfc_dosage_usage_review",
            confidence="high",
            score=1.0,
            brand="CFC",
        )

        enforced = chat_pipeline._enforce_customer_grounding(
            ChatPipelineRequest(brand="cfc", sender_id=sender_id, text="Bón sao?"),
            response,
        )

        self.assertEqual(enforced.intent, "cfc_grounded_fallback")
        self.assertEqual(enforced.fallback_reason, "UNSUPPORTED_GENERATOR_SOURCE")
        self.assertNotIn("200kg/ha", enforced.answer)

    async def test_location_attachment_is_acknowledged_without_fake_nearest_dealer(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="live-location",
                text="",
                input_kind="location",
                attachment_type="location",
                latitude=10.1092,
                longitude=105.6235,
            ))

        self.assertEqual(result.intent, "cfc_dealer_location_received")
        self.assertIn("đã nhận vị trí", result.answer)
        self.assertIn("chưa có đủ dữ liệu", result.answer)
        self.assertNotIn("đại lý gần nhất là", result.answer.lower())
        state = chat_pipeline._local_session_cache[
            "cfc:session:messenger:live-location"
        ]["conversation_state"]
        self.assertEqual(state["confirmed_slots"]["location"]["latitude"], 10.1092)

    async def test_cfc_phone_request_does_not_invent_or_reuse_zeo_hotline(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        with redis_patch, faq_patch, profile_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="cfc-contact",
                text="Cho mình xin số hotline chăm sóc khách hàng Cò Bay",
            ))

        self.assertEqual(result.intent, "cfc_contact_information_unavailable")
        self.assertIn("chưa có số hotline", result.answer)
        self.assertIn("https://cfccobay.com", result.answer)
        self.assertNotIn("1900 5307", result.answer)
        self.assertNotIn("0292 3841 818", result.answer)

    async def test_unknown_cfc_question_never_calls_generative_answer(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        ai_answer = AsyncMock(return_value="Thông tin tự suy đoán")
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=AsyncMock(return_value={
                    "answer": "", "intent": "", "score": 0.0, "source_id": "",
                })), \
                patch("chat_pipeline.reason_and_answer_cskh", new=ai_answer), \
                patch("chat_pipeline.notify_admin_unanswered", new=AsyncMock()):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="strict-grounding",
                text="Phân này có chống chịu mặn tuyệt đối không?",
            ))

        ai_answer.assert_not_awaited()
        self.assertEqual(result.intent, "cfc_grounded_fallback")
        self.assertIn("chưa tìm được thông tin phù hợp", result.answer)
        self.assertNotIn("knowledge cfc", result.answer.lower())
        self.assertNotIn("tự suy đoán", result.answer.lower())
        self.assertEqual(result.fallback_reason, "NO_GROUNDED_KNOWLEDGE")

    async def test_sourced_cfc_rag_answer_is_not_rewritten_by_llm(self):
        redis_patch, faq_patch, profile_patch, nlu_patch = self._patches()
        synthesizer = AsyncMock(return_value="Câu trả lời có fact được tự thêm")
        with redis_patch, faq_patch, profile_patch, nlu_patch, \
                patch("chat_pipeline.semantic_search", new=AsyncMock(return_value={
                    "answer": "Nội dung nguyên bản từ Knowledge CFC.",
                    "intent": "support_general",
                    "score": 0.91,
                    "source_id": "test:cfc:knowledge",
                    "answer_mode": "rewrite",
                })), \
                patch("chat_pipeline.synthesize_cskh_answer", new=synthesizer):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="strict-rag-rewrite",
                text="Mình cần hỏi một nội dung hỗ trợ CFC",
            ))

        synthesizer.assert_not_awaited()
        self.assertEqual(result.answer, "Nội dung nguyên bản từ Knowledge CFC.")
        self.assertEqual(result.intent, "support_general")
        trace = chat_pipeline._local_session_cache[
            "cfc:session:messenger:strict-rag-rewrite"
        ]["last_trace"]
        self.assertEqual(trace["source_id"], "test:cfc:knowledge")


if __name__ == "__main__":
    unittest.main()
