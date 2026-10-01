"""
eval_test_suite.py — Bộ Kiểm Thử Ngữ Nghĩa Toàn Diện cho Chatbot ZeO & CFC
Đánh giá độ chính xác phân loại Intent, Nội dung câu trả lời, Điểm tin cậy và Tốc độ xử lý.
"""

from rag_search import get_redis
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from chat_pipeline import process_chat_pipeline, ChatPipelineRequest

TEST_CASES = [
    # ─── 1. CHÀO HỎI & CẢM ƠN ───
    {"q": "Xin chào shop", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Hello ZeO", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Shop ơi", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Alo có ai trực không", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Hi bạn", "category": "greeting", "expected_intent": "greeting"},
    {"q": "Cảm ơn shop nhiều", "category": "thanks", "expected_intent": "thanks"},
    {"q": "Ok thanks bạn", "category": "thanks", "expected_intent": "thanks"},
    {"q": "Dạ cảm ơn shop", "category": "thanks", "expected_intent": "thanks"},

    # ─── 2. DANH MỤC SẢN PHẨM TỔNG QUAN ───
    {"q": "ZeO có những sản phẩm gì?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Cho tôi hỏi về các sản phẩm của ZeO", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "ZeO bán những gì?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Bên mình có những loại nào?", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Danh mục sản phẩm của ZeO", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Giới thiệu các dòng sản phẩm ZeO đi", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "Các nhóm sản phẩm của shop", "category": "catalog", "expected_intent": "catalog_overview"},
    {"q": "PANO là sản phẩm gì?", "category": "catalog", "expected_intent": "pano_product_type"},
    {"q": "Pano có những dòng nào?", "category": "catalog", "expected_intent": "pano_product_type"},

    # ─── 3. KHUYẾN MÃI, SALE & VOUCHER ───
    {"q": "Hiện tại có sản phẩm nào đang sale hay ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "có sản phẩm nào đang sale ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có sản phẩm nào đang sale ở shopee ko", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Shop có đang khuyến mãi gì không?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có voucher giảm giá shopee không?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Đang có ưu đãi gì thế shop?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Có mã giảm giá không bạn?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Sản phẩm nào đang giảm giá?", "category": "promotion", "expected_intent": "promotion_deals"},
    {"q": "Shopee có sale không?", "category": "promotion", "expected_intent": "promotion_deals"},

    # ─── 4. MUA HÀNG & LINK SHOPEE ───
    {"q": "xin link shopee ạ", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho mình link shopee chính hãng", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Mua hàng online ở đâu?", "category": "purchase", "expected_intent": "online_purchase"},
    {"q": "Tôi muốn mua nước giặt thì mua ở đâu?", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho xin link nước rửa chén shopee", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Cho xin link nước lau sàn", "category": "purchase", "expected_intent": "shopee_product_link"},
    {"q": "Giá bao nhiêu?", "category": "pricing", "expected_intent": "zeo_price_inquiry_general"},
    {"q": "Nước giặt giá bao nhiêu tiền 1 can?", "category": "pricing", "expected_intent": "zeo_price_inquiry_general"},
    {"q": "sản phẩm nào mắc nhất nhỉ", "category": "pricing", "expected_intent": "shopee_price_extreme"},

    # ─── 5. TÍNH NĂNG, CÔNG NGHỆ & CHỨNG NHẬN ───
    {"q": "Bột giặt ZeO dùng công nghệ gì?", "category": "tech", "expected_intent": "zeo_detergent_technology"},
    {"q": "Enzyme Thụy Điển có trong sản phẩm nào?", "category": "tech", "expected_intent": "zeo_detergent_technology"},
    {"q": "Bột giặt ZeO có chứng nhận gì của Viện Pasteur không?", "category": "tech", "expected_intent": "zeo_detergent_certification"},
    {"q": "Bột giặt ZeO có thơm lâu không?", "category": "tech", "expected_intent": "zeo_detergent_fragrance"},
    {"q": "PANO có những mùi hương nào?", "category": "tech", "expected_intent": "pano_laundry_fragrance_options"},
    {"q": "Công nghệ VEILEX là gì?", "category": "tech", "expected_intent": "pano_veilex_odor_control"},
    {"q": "Nước lau sàn có những mùi nào?", "category": "tech", "expected_intent": "zeo_floor_cleaner_product_overview"},
    {"q": "Nước rửa chén ZIF ZeO có thành phần gì?", "category": "tech", "expected_intent": "zeo_zif_dishwashing_liquid"},
    {"q": "Tẩy Toilet ZeO có diệt khuẩn không?", "category": "tech", "expected_intent": "zeo_toilet_cleaner"},

    # ─── 6. GIAO HÀNG & PHÍ SHIP ───
    {"q": "Có giao hàng toàn quốc không?", "category": "shipping", "expected_intent": "nationwide_shipping_no_cod"},
    {"q": "Shop có ship không?", "category": "shipping", "expected_intent": "nationwide_shipping_no_cod"},
    {"q": "Giao hàng mấy ngày thì tới?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},
    {"q": "Phí ship bao nhiêu tiền?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},
    {"q": "Có freeship không shop?", "category": "shipping", "expected_intent": "shipping_time_and_fee"},

    # ─── 7. CHÍNH SÁCH ĐỔI TRẢ & BẢO HÀNH ───
    {"q": "Chính sách đổi trả như thế nào?", "category": "policy", "expected_intent": "return_policy_scope"},
    {"q": "Mua trên Shopee có được đổi trả không?", "category": "policy", "expected_intent": "return_policy_scope"},
    {"q": "Hàng bị lỗi rách nắp có được đổi không?", "category": "policy", "expected_intent": "return_eligible_cases"},
    {"q": "Thời hạn khiếu nại đổi trả là bao lâu?", "category": "policy", "expected_intent": "return_claim_deadlines"},
    {"q": "Quy trình đổi trả hàng thế nào?", "category": "policy", "expected_intent": "return_process"},
    {"q": "Bao lâu thì nhận được tiền hoàn trả?", "category": "policy", "expected_intent": "refund_processing_time"},

    # ─── 8. ĐẠI LÝ & LẤY SỈ ───
    {"q": "Tôi muốn lấy sỉ thì làm sao?", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Muốn làm đại lý phân phối ZeO", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Có chính sách sỉ cho đại lý không?", "category": "wholesale", "expected_intent": "wholesale_inquiry"},
    {"q": "Tôi muốn nhập số lượng lớn về bán", "category": "wholesale", "expected_intent": "wholesale_inquiry"},

    # ─── 9. ĐỊA CHỈ & GIỜ MỞ CỬA ───
    {"q": "Shop mở cửa lúc mấy giờ?", "category": "operations", "expected_intent": "shop_opening_hours"},
    {"q": "Hôm nay shop có mở cửa không?", "category": "operations", "expected_intent": "shop_opening_hours"},
    {"q": "Địa chỉ công ty ở đâu?", "category": "operations", "expected_intent": "company_address"},
    {"q": "Hotline liên hệ là số mấy?", "category": "operations", "expected_intent": "company_contact_information"},

    # ─── 10. KHÁCH ĐỂ LẠI SĐT ───
    {"q": "Tôi ở Cần Thơ, số điện thoại 0918123456", "category": "lead", "expected_intent": "contact_phone_provided"},
    {"q": "Tư vấn cho mình qua số 0907123456 nhé", "category": "lead", "expected_intent": "contact_phone_provided"},

    # ─── 11. CÂU HỎI LẠ (CHƯA CÓ TRONG FAQ) → KIỂM TRA FALLBACK TRUNG THỰC ───
    {"q": "Bên mình có chi nhánh cửa hàng tại Đà Lạt không bạn?", "category": "unindexed", "expected_intent": "unanswered_query"},
    {"q": "Có ship hỏa tốc 2 giờ tại Sài Gòn không?", "category": "unindexed", "expected_intent": "unanswered_query"},
    {"q": "Có can 20 lít không bạn?", "category": "unindexed", "expected_intent": "unanswered_query"},

    # ─── 12. REGRESSION: CÁC CÂU HỎI THẬT DỄ BỊ RAG BẮT NHẦM ───
    {"q": "Dòng sản phẩm ZiF", "category": "regression_specific_product", "expected_intent": "zeo_zif_dishwashing_liquid"},
    {"q": "Nước giặt Pano", "category": "regression_specific_product", "expected_intent": "pano_product_type"},
    {"q": "Giới thiệu cty đi", "category": "regression_company", "expected_intent": "company_overview"},
    {"q": "Sơ lược về cty", "category": "regression_company", "expected_intent": "company_overview"},
    {"q": "CFC homecare là của cty luôn đúng không", "category": "regression_company", "expected_intent": "company_overview"},
    {"q": "Sdt", "category": "regression_contact", "expected_intent": "company_contact_information"},
    {"q": "Sdt công tu", "category": "regression_contact", "expected_intent": "company_contact_information"},
    {"q": "Cho số chăm sóc kh cty zeo cần thơ", "category": "regression_contact", "expected_intent": "company_contact_information"},
    {"q": "Có bột giặt Omo không", "category": "regression_unsupported", "expected_intent": "competitor_product_unavailable"},
    {"q": "Tiktok", "category": "regression_channel", "expected_intent": "official_channel_unverified"},
    {"q": "Zalo", "category": "regression_channel", "expected_intent": "official_channel_unverified"},
    {"q": "Sản phẩm mới nhất của cty", "category": "regression_unverified", "expected_intent": "new_product_unverified"},
    {"q": "Sai địa chỉ rồi", "category": "regression_feedback", "expected_intent": "customer_correction_review"},
    {"q": "Để tôi chỉnh lại cho", "category": "regression_feedback", "expected_intent": "customer_correction_review"},
    {"q": "Có giấy tờ chứng minh công nghệ đó không", "category": "regression_proof", "expected_intent": "zeo_detergent_certification"},
    {"q": "1kg bột cho 5 bộ đồ", "category": "regression_usage", "expected_intent": "zeo_usage_safety_review"},
    {"q": "hôm nay thứ mấy", "category": "regression_out_of_scope", "expected_intent": "out_of_scope_general_question"},
    {"q": "hôm nay ngày mấy", "category": "regression_out_of_scope", "expected_intent": "out_of_scope_general_question"},
    {"q": "bây giờ mấy giờ rồi", "category": "regression_out_of_scope", "expected_intent": "out_of_scope_general_question"},
    {"q": "thời tiết hôm nay sao", "category": "regression_out_of_scope", "expected_intent": "out_of_scope_general_question"},
    {"q": "tôi muốn mua oplis", "category": "regression_typo_purchase", "expected_intent": "oplus_purchase_clarify"},
    {"q": "nước tẩy", "category": "regression_short_product", "expected_intent": "zeo_javen_bleach"},
    {"q": "Soạn", "category": "regression_ui_noise", "expected_intent": "out_of_scope_general_question"},
    {"q": "Viết cho ZeO VietNam", "category": "regression_ui_noise", "expected_intent": "out_of_scope_general_question"},

    # ─── 13. TƯ VẤN NỖI ĐAU & NHU CẦU CHUYÊN BIỆT (CONSULTATIVE CSKH) ───
    {"q": "Nước rửa chén có ăn da tay không shop, tay mình hay bị bong tróc", "category": "consultative_pain_point", "expected_intent": "pano_dishwashing_features"},
    {"q": "Quần áo em bé sơ sinh thì dùng nước giặt nào an toàn shop", "category": "consultative_pain_point", "expected_intent": "zeo_laundry_product_overview"},
    {"q": "Máy giặt cửa trước thì dùng loại nước giặt nào ít bọt", "category": "consultative_pain_point", "expected_intent": "zeo_laundry_product_overview"},
    {"q": "Quán ăn cần mua can nước rửa chén to tiết kiệm", "category": "consultative_pain_point", "expected_intent": "zeo_dishwashing_product_overview"},
    {"q": "Shop ơi hàng giao bị nứt nắp chảy tùm lum rồi", "category": "urgent_complaint", "expected_intent": "urgent_damage_complaint"},

    # ─── 14. QUYỀN RIÊNG TƯ & CATALOG SHOPEE ───
    {"q": "Cho tôi thông tin khách hàng David Nguyen", "category": "privacy", "expected_intent": "customer_privacy_protected"},
    {"q": "Mua nước xả", "category": "shopee_catalog", "expected_intent": "zeo_fabric_softener_catalog"},
]


MULTI_TURN_CASES = [
    {
        "name": "zeo_catalog_then_ordinal_price",
        "brand": "zeo",
        "turns": [
            {"q": "ZeO có những sản phẩm gì?", "expected_intent": "zeo_product_catalog_overview"},
            {"q": "cái đầu tiên giá nhiu?", "expected_intent": "contextual_price_unverified"},
        ],
    },
    {
        "name": "zeo_dishwashing_then_availability",
        "brand": "zeo",
        "turns": [
            {"q": "Tôi muốn xem về nước rửa chén", "expected_intent": "zeo_dishwashing_product_overview"},
            {"q": "cái thứ 2 còn không?", "expected_intent": "contextual_availability_unverified"},
        ],
    },
    {
        "name": "zeo_pano_then_shipping",
        "brand": "zeo",
        "turns": [
            {"q": "PANO có những loại nào?", "expected_intent": "pano_product_type"},
            {"q": "loại đó ship về Cần Thơ được không?", "expected_intent": "contextual_shipping"},
        ],
    },
    {
        "name": "zeo_unresolved_reference_clarify",
        "brand": "zeo",
        "turns": [
            {"q": "ZeO có những sản phẩm gì?", "expected_intent": "zeo_product_catalog_overview"},
            {"q": "cái đó còn hàng không?", "expected_intent": "context_reference_clarify"},
        ],
    },
    {
        "name": "cfc_catalog_then_ordinal_price",
        "brand": "cfc",
        "turns": [
            {"q": "CFC có những dòng phân nào?", "expected_intent": "product_lines"},
            {"q": "cái thứ 2 giá sao?", "expected_intent": "contextual_price_unverified"},
        ],
    },
    {
        "name": "cfc_catalog_then_dosage_guardrail",
        "brand": "cfc",
        "turns": [
            {"q": "CFC có những dòng phân nào?", "expected_intent": "product_lines"},
            {"q": "cái thứ 2 bón bao nhiêu kg cho 1 công lúa?", "expected_intent": "cfc_dosage_usage_review"},
        ],
    },
    {
        "name": "zeo_technology_context_followups",
        "brand": "zeo",
        "turns": [
            {"q": "Có giấy tờ chứng minh công nghệ đó không?", "expected_intent": "zeo_detergent_certification"},
            {"q": "có công nghệ gì", "expected_intent": "contextual_technology_more_info"},
            {"q": "còn công nghệ nào khác ko", "expected_intent": "contextual_technology_more_info"},
            {"q": "còn gì nữa ko", "expected_intent": "contextual_product_more_info"},
        ],
    },
    {
        "name": "zeo_usage_context_followup",
        "brand": "zeo",
        "turns": [
            {"q": "1kg bột giặt cho 5 bộ đồ được ko", "expected_intent": "zeo_usage_safety_review"},
            {"q": "vậy 2 bộ thì sao", "expected_intent": "zeo_usage_safety_review"},
        ],
    },
    {
        "name": "zeo_compound_budget_then_stain_followup",
        "brand": "zeo",
        "turns": [
            {"q": "có sản phẩm nào dưới 200k ko nhỉ, có giao về rạch giá đc ko", "expected_intent": "multi_shopee_budget_filter_shipping_time_and_fee"},
            {"q": "Cái số 2 dùng ổn ko nhỉ , liệu có tẩy được vết máu ko", "expected_intent": "laundry_stain_removal_guide"},
            {"q": "cái này tẩy được vết máu ko sốp", "expected_intent": "laundry_stain_removal_guide"},
        ],
    },
    {
        "name": "zeo_budget_result_then_direct_product_link",
        "brand": "zeo",
        "turns": [
            {"q": "vậy có sản phẩm nào khoảng 200k ko nhỉ", "expected_intent": "shopee_budget_filter"},
            {
                "q": "xin link sản phẩm đó đi",
                "expected_intent": "shopee_product_link",
                "expect_direct_product_link": True,
            },
        ],
    },
    {
        "name": "zeo_catalog_then_most_expensive_price",
        "brand": "zeo",
        "turns": [
            {"q": "sản phẩm nào mắc nhất nhỉ", "expected_intent": "shopee_price_extreme"},
            {
                "q": "giá cái nào mắc nhất",
                "expected_intent": "shopee_price_extreme",
                "expect_answer_contains": "681.812",
                "expect_answer_not_contains": "147.582",
            },
        ],
    },
    {
        "name": "zeo_return_contact_then_fee_typo",
        "brand": "zeo",
        "turns": [
            {"q": "Trả hàng", "expected_intent": "return_eligible_cases"},
            {"q": "Liên hệ sao để trả hàng", "expected_intent": "return_process"},
            {
                "q": "Điện có tốn phí không",
                "expected_intent": "return_fee_unverified",
                "expect_answer_not_contains": "thời gian giao hàng",
            },
        ],
    },
    {
        "name": "zeo_fabric_softener_catalog_consistency",
        "brand": "zeo",
        "turns": [
            {"q": "Mua nước xả", "expected_intent": "zeo_fabric_softener_catalog"},
            {"q": "Có nước xả ko", "expected_intent": "zeo_fabric_softener_catalog"},
            {
                "q": "Xả vải ZeO",
                "expected_intent": "zeo_fabric_softener_catalog",
                "expect_answer_contains": "Nano Clean",
                "expect_answer_not_contains": "Tẩy Màu",
            },
        ],
    },
    {
        "name": "zeo_catalog_group_three_products",
        "brand": "zeo",
        "turns": [
            {"q": "Có sp gì vậy shop", "expected_intent": "zeo_product_catalog_overview"},
            {
                "q": "Cái số 3 có sản phẩm nào thế",
                "expected_intent": "zeo_floor_cleaner_product_overview",
                "expect_answer_not_contains": "tồn kho",
            },
        ],
    },
]


async def run_eval():
    print(f"🚀 BẮT ĐẦU CHẠY BỘ ĐÁNH GIÁ CHATBOT ({len(TEST_CASES)} SINGLE-TURN + {len(MULTI_TURN_CASES)} MULTI-TURN)...")
    print("=" * 80)

    passed = 0
    failed = 0
    total_latency = 0.0

    results_by_cat = {}

    run_id = int(time.time() * 1000)
    for idx, tc in enumerate(TEST_CASES, 1):
        q = tc["q"]
        cat = tc["category"]
        expected = tc["expected_intent"]

        req = ChatPipelineRequest(brand="zeo", sender_id=f"eval_user_{run_id}_{idx}", text=q)
        t0 = time.perf_counter()
        res = await process_chat_pipeline(req)
        latency = (time.perf_counter() - t0) * 1000
        total_latency += latency

        matched = (res.intent == expected)
        if matched:
            passed += 1
            status = "✅ PASS"
        else:
            # Chấp nhận một số intent tương đương hợp lý
            if (expected in ["shopee_product_link", "online_purchase"] and res.intent in ["shopee_product_link", "online_purchase"]) \
               or (expected in ["promotion_deals", "zeo_promotions_and_deals"] and res.intent in ["promotion_deals", "zeo_promotions_and_deals"]) \
               or (expected in ["catalog_overview", "zeo_product_catalog_overview"] and res.intent in ["catalog_overview", "zeo_product_catalog_overview"]) \
               or (expected in ["shipping_time_and_fee", "nationwide_shipping_no_cod"] and res.intent in ["shipping_time_and_fee", "nationwide_shipping_no_cod"]) \
               or (expected in ["floor_cleaner_features", "zeo_floor_cleaner_product_overview"] and res.intent in ["floor_cleaner_features", "zeo_floor_cleaner_product_overview"]) \
               or (expected in ["zeo_dishwashing_product_overview", "pano_dishwashing_product_overview", "pano_dishwashing_features"] and res.intent in ["zeo_dishwashing_product_overview", "pano_dishwashing_product_overview", "pano_dishwashing_features"]) \
               or (expected in ["zeo_laundry_product_overview", "zeo_laundry_brand_differences"] and res.intent in ["zeo_laundry_product_overview", "zeo_laundry_brand_differences"]):
                matched = True
                passed += 1
                status = "✅ PASS (Synonym)"
            else:
                failed += 1
                status = f"❌ FAIL (Got: {res.intent}, Expected: {expected})"

        if cat not in results_by_cat:
            results_by_cat[cat] = {"total": 0, "passed": 0}
        results_by_cat[cat]["total"] += 1
        if matched:
            results_by_cat[cat]["passed"] += 1

        print(f"[{idx:02d}/{len(TEST_CASES)}] {status} | Latency: {latency:.1f}ms")
        print(f"   Q: \"{q}\"")
        print(f"   A: {res.answer[:120]}...\n")

    print("=" * 80)
    print("🧠 KIỂM TRA HỘI THOẠI NHIỀU LƯỢT / CONTEXT MEMORY:")
    for case_idx, case in enumerate(MULTI_TURN_CASES, 1):
        sender_id = f"eval_context_user_{case_idx}_{int(time.time() * 1000)}"
        case_passed = True
        print(f"\n[{case_idx:02d}/{len(MULTI_TURN_CASES)}] {case['name']}")
        for turn_idx, turn in enumerate(case["turns"], 1):
            # pyrefly: ignore [bad-argument-type, bad-index]
            req = ChatPipelineRequest(brand=case["brand"], sender_id=sender_id, text=turn["q"])
            t0 = time.perf_counter()
            res = await process_chat_pipeline(req)
            latency = (time.perf_counter() - t0) * 1000
            total_latency += latency
            # pyrefly: ignore [bad-index]
            matched = (res.intent == turn["expected_intent"]) or (
                # pyrefly: ignore [bad-index]
                turn["expected_intent"] == "contextual_price_unverified" and res.intent in ["contextual_price_unverified", "specific_product_pricing"]
            )
            # pyrefly: ignore [missing-attribute]
            if turn.get("expect_direct_product_link"):
                general_store_urls = {
                    "https://shopee.vn/zeovietnamofficial",
                    "https://shopee.vn/cfccobay",
                }
                matched = matched and bool(res.shopee_url) and res.shopee_url not in general_store_urls
            # pyrefly: ignore [missing-attribute]
            if turn.get("expect_answer_contains"):
                matched = matched and str(turn["expect_answer_contains"]) in res.answer
            # pyrefly: ignore [missing-attribute]
            if turn.get("expect_answer_not_contains"):
                matched = matched and str(turn["expect_answer_not_contains"]) not in res.answer
            case_passed = case_passed and matched
            print(
                f"   Turn {turn_idx}: {'✅' if matched else '❌'} "
                # pyrefly: ignore [bad-index]
                f"Got={res.intent} Expected={turn['expected_intent']} | {latency:.1f}ms"
            )
            # pyrefly: ignore [bad-index]
            print(f"      Q: \"{turn['q']}\"")
            print(f"      A: {res.answer[:120]}...")
            await asyncio.sleep(0.08)

        if case_passed:
            passed += 1
        else:
            failed += 1

    print("=" * 80)
    print("📊 BẢNG TỔNG KẾT ĐÁNH GIÁ CHẤT LƯỢNG NLU:")
    total_cases = len(TEST_CASES) + len(MULTI_TURN_CASES)
    total_latency_divisor = len(TEST_CASES) + sum(len(case["turns"]) for case in MULTI_TURN_CASES)
    print(f"• Tổng số test cases: {total_cases}")
    print(f"• Thành công: {passed}/{total_cases} ({passed/total_cases*100:.1f}%)")
    print(f"• Thất bại: {failed}/{total_cases}")
    print(f"• Tốc độ trung bình: {total_latency/total_latency_divisor:.1f}ms/câu")
    print("\nChi tiết theo nhóm:")
    for cat, stat in results_by_cat.items():
        pct = (stat['passed'] / stat['total']) * 100
        print(f"  - {cat:15s}: {stat['passed']}/{stat['total']} ({pct:.0f}%)")
    print("=" * 80)

    try:
        r = await get_redis()
        await r.close()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(run_eval())
