import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from chat_pipeline import (  # noqa: E402
    ChatPipelineRequest,
    _looks_like_availability_request,
    _normalize_vn,
    process_chat_pipeline,
)


class FakeRedis:
    async def get(self, key):
        return None


FAQS = {
    "company_contact_information": (
        "Địa chỉ Công ty: Trục Chính Khu Công Nghiệp Trà Nóc 1, Cần Thơ | "
        "Hotline CSKH: 1900 5307 | Website: https://zeo.vn/"
    ),
    "return_eligible_cases": "Hàng lỗi sản xuất, giao sai hoặc hư hỏng vận chuyển đủ điều kiện để CSKH kiểm tra đổi trả.",
    "return_process": "Quy trình đổi trả: liên hệ hotline 1900 5307, gửi mã đơn và ảnh/video; CSKH xác nhận rồi thu hồi hoặc hoàn tiền.",
    "return_claim_deadlines": "Lỗi vận chuyển cần báo trong 24 giờ; lỗi chất lượng cần báo trong 7 ngày.",
    "zeo_product_catalog_overview": (
        "Dạ ZeO có 4 nhóm: 1. Giặt giũ; 2. Rửa chén; "
        "3. Lau sàn; 4. Tẩy rửa vệ sinh."
    ),
    "zeo_floor_cleaner_product_overview": (
        "Dạ nhóm lau sàn hiện có Nước lau sàn ZeO và Oplus với 5 hương: "
        "Y Lan, Bạc Hà, Sả Chanh, Hoa Hạ và Baby."
    ),
    "cfc_dealer_location_request": (
        "Dạ bạn gửi giúp mình số điện thoại và khu vực/tỉnh thành cụ thể. "
        "Admin sẽ chuyển nhà phân phối gần nhất liên hệ ạ."
    ),
    "cfc_cross_brand_out_of_scope": (
        "Dạ CFC Cò Bay là thương hiệu phân bón; sản phẩm gia dụng thuộc hệ ZeO/PANO/Oplus."
    ),
}


async def fake_faq(brand, intent):
    answer = FAQS.get(intent, "")
    return {"intent": intent, "answer": answer, "source_id": f"test:{intent}"} if answer else {}


class ConversationRegressionGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()
        self.catalog = [
            {
                "item_id": "42401783886",
                "name": "Combo 10 gói Nước xả vải Nano Clean ZeO",
                "brand": "ZeO",
                "category": "Nước xả vải",
                "price": 17_100,
                "in_stock": True,
                "link_shopee": "https://shopee.vn/softener-small",
            },
            {
                "item_id": "56612838999",
                "name": "Nước xả vải Nano Clean ZeO can 1kg 3.8kg",
                "brand": "ZeO",
                "category": "Nước xả vải",
                "price": 83_200,
                "in_stock": True,
                "link_shopee": "https://shopee.vn/softener-large",
            },
        ]

    def _common_patches(self):
        return (
            patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())),
            patch("chat_pipeline._async_save_session", new=AsyncMock()),
            patch("chat_pipeline.get_faq_by_intent", side_effect=fake_faq),
            patch("chat_pipeline._llm_nlu_config", return_value=("off", 0.3, 0.72)),
        )

    async def test_return_flow_keeps_context_for_contact_and_fee_typo(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="return-flow", text="Trả hàng"
            ))
            second = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="return-flow", text="Liên hệ sao để trả hàng"
            ))
            third = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="return-flow", text="Điện có tốn phí không"
            ))

        self.assertEqual(first.intent, "return_eligible_cases")
        self.assertEqual(second.intent, "return_process")
        self.assertIn("1900 5307", second.answer)
        self.assertEqual(third.intent, "return_fee_unverified")
        self.assertNotIn("phí ship", third.answer.lower())

    async def test_return_flow_is_cleared_when_customer_changes_topic(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="return-flow-reset", text="Trả hàng"
            ))
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="return-flow-reset", text="Có sp gì vậy shop"
            ))

        self.assertEqual(result.intent, "zeo_product_catalog_overview")
        session = chat_pipeline._local_session_cache[
            "zeo:session:messenger:return-flow-reset"
        ]
        self.assertEqual(session["conversation_state"]["active_flow"]["name"], "")

    async def test_third_party_customer_lookup_is_blocked_before_rag(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="privacy-flow",
                text="Cho tôi thông tin khách hàng David Nguyen",
            ))

        self.assertEqual(result.intent, "customer_privacy_protected")
        self.assertIn("quyền riêng tư", result.answer)
        self.assertNotIn("zeo.vn", result.answer)

    async def test_fabric_softener_questions_use_catalog_not_stale_faq(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch, \
                patch("shopee_matcher.load_shopee_catalog", return_value=self.catalog):
            for index, query in enumerate(("Mua nước xả", "Có nước xả ko", "Xả vải ZeO"), start=1):
                result = await process_chat_pipeline(ChatPipelineRequest(
                    brand="zeo",
                    sender_id=f"softener-flow-{index}",
                    text=query,
                ))
                self.assertEqual(result.intent, "zeo_fabric_softener_catalog")
                self.assertIn("Nano Clean ZeO", result.answer)
                self.assertNotIn("Tẩy Màu", result.answer)
                self.assertNotIn("chưa có thông tin", result.answer)

    async def test_catalog_group_three_is_product_view_not_availability(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            first = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="catalog-group", text="Có sp gì vậy shop"
            ))
            second = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="catalog-group", text="Cái số 3 có sản phẩm nào thế"
            ))

        self.assertEqual(first.intent, "zeo_product_catalog_overview")
        self.assertEqual(second.intent, "zeo_floor_cleaner_product_overview")
        self.assertIn("lau sàn", second.answer.lower())

    def test_availability_detector_does_not_confuse_co_san_pham(self):
        self.assertFalse(_looks_like_availability_request(_normalize_vn("có sản phẩm nào thế")))
        self.assertTrue(_looks_like_availability_request(_normalize_vn("có sẵn hàng không")))

    async def test_cskh_abbreviation_routes_to_sheet_contact_without_fake_area(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo",
                sender_id="contact-abbreviation",
                text="Cho số chăm sóc kh cty zeo cần thơ",
            ))

        self.assertEqual(
            _normalize_vn("Cho số chăm sóc kh cty zeo cần thơ"),
            "cho so cham soc khach hang cong ty zeo can tho",
        )
        self.assertEqual(_normalize_vn("còn hàng kh"), "con hang khong")
        for query in (
            "Số CSKH ZeO",
            "Xin số chăm sóc khách hàng công ty",
            "Cho mình số của cty",
            "CSKH ZeO số mấy",
        ):
            with self.subTest(query=query):
                self.assertEqual(
                    chat_pipeline._detect_contact_intent(_normalize_vn(query), "zeo"),
                    "company_contact_information",
                )
        self.assertEqual(result.intent, "company_contact_information")
        self.assertIn("1900 5307", result.answer)
        self.assertEqual(result.area, "")
        trace = chat_pipeline._local_session_cache[
            "zeo:session:messenger:contact-abbreviation"
        ]["last_trace"]
        self.assertEqual(trace["source_id"], "test:company_contact_information")

    async def test_shadow_nlu_records_trace_without_overriding_legacy_route(self):
        catalog = self.catalog + [{
            "item_id": "MAX",
            "name": "Thùng nước giặt Pano giá cao nhất",
            "brand": "PANO",
            "category": "Nước giặt",
            "price": 681_812,
            "in_stock": True,
            "link_shopee": "https://shopee.vn/max",
        }]
        shadow_scheduler = Mock(return_value="scheduled")

        with patch("chat_pipeline.get_redis", new=AsyncMock(return_value=FakeRedis())), \
                patch("chat_pipeline._async_save_session", new=AsyncMock()), \
                patch("chat_pipeline._llm_nlu_config", return_value=("shadow", 0.3, 0.72)), \
                patch("chat_pipeline.schedule_nlu_shadow", shadow_scheduler), \
                patch("shopee_matcher.load_shopee_catalog", return_value=catalog):
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="zeo", sender_id="shadow-flow", text="sản phẩm nào mắc nhất nhỉ"
            ))

        self.assertEqual(result.intent, "shopee_price_extreme")
        shadow_scheduler.assert_called_once()
        trace = chat_pipeline._local_session_cache["zeo:session:messenger:shadow-flow"]["last_trace"]
        self.assertEqual(trace["llm_nlu"]["mode"], "shadow")
        self.assertEqual(trace["llm_nlu"]["status"], "scheduled")
        self.assertFalse(trace["llm_nlu"]["affects_response"])

    async def test_cfc_dealer_location_does_not_fall_into_profile_recall(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="dealer-location",
                text="Ở khu vực tôi có đại lý không",
            ))

        self.assertEqual(result.intent, "cfc_dealer_location_request")
        self.assertEqual(result.lead_stage, "collecting_contact")
        session = chat_pipeline._local_session_cache["cfc:session:messenger:dealer-location"]
        self.assertEqual(set(session["conversation_state"]["pending_slots"]), {"phone", "area"})
        self.assertEqual(session["last_trace"]["source_id"], "test:cfc_dealer_location_request")

    async def test_cfc_cross_brand_fast_path_keeps_sheet_source(self):
        redis_patch, save_patch, faq_patch, nlu_patch = self._common_patches()
        with redis_patch, save_patch, faq_patch, nlu_patch:
            result = await process_chat_pipeline(ChatPipelineRequest(
                brand="cfc",
                sender_id="cross-brand",
                text="CFC có nước giặt PANO không",
            ))

        self.assertEqual(result.intent, "cfc_cross_brand_out_of_scope")
        trace = chat_pipeline._local_session_cache["cfc:session:messenger:cross-brand"]["last_trace"]
        self.assertEqual(trace["source_id"], "test:cfc_cross_brand_out_of_scope")


if __name__ == "__main__":
    unittest.main()
