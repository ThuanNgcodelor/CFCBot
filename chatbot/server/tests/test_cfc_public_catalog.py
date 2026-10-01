import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.catalog import (  # noqa: E402
    is_public_fertilizer_item,
    parse_snapshot,
    search_public_fertilizers,
)
import chat_pipeline  # noqa: E402


class CfcPublicCatalogTests(unittest.TestCase):
    def setUp(self):
        self.items = [
            {"product_name": "NPK Cò bay 20-10-10 bao 25kg", "product_code": "01.00377", "product_category": "PHÂN NPK"},
            {"product_name": "NPK Cò bay 20-20-10 bao 25kg", "product_code": "01.EXACT", "product_category": "PHÂN NPK"},
            {"product_name": "Áo mưa Cò Bay", "product_code": "NO", "product_category": ""},
            {"product_name": "Bột giặt bao jumbo 500kg", "product_code": "NO2", "product_category": ""},
        ]

    def test_non_fertilizer_export_rows_are_not_public(self):
        self.assertTrue(is_public_fertilizer_item(self.items[0]))
        self.assertFalse(is_public_fertilizer_item(self.items[2]))
        self.assertFalse(is_public_fertilizer_item(self.items[3]))

    def test_formula_query_is_exact_and_does_not_substitute_near_match(self):
        result = search_public_fertilizers(self.items, "Có NPK 20-20-10 không", limit=3)
        self.assertEqual([item["product_code"] for item in result], ["01.EXACT"])
        result = search_public_fertilizers([self.items[0]], "Có NPK 20-20-10 không", limit=3)
        self.assertEqual(result, [])

    def test_explicit_organic_category_does_not_leak_npk_rows(self):
        items = [
            {"product_name": "Hữu cơ Cò Bay 30%", "product_code": "HC30", "product_category": "PHÂN HỮU CƠ"},
            self.items[0],
        ]
        result = search_public_fertilizers(items, "Cho tôi xem phân hữu cơ Cò Bay", limit=5)
        self.assertEqual([item["product_code"] for item in result], ["HC30"])

    def test_snapshot_parser_handles_bytes_and_projection_is_small(self):
        items = parse_snapshot('{"items": [{"product_name": "NPK Cò bay 15-15-15", "product_code": "15"}]}'.encode())
        result = search_public_fertilizers(items, "NPK", limit=3)
        self.assertEqual(result[0]["product_code"], "15")
        self.assertNotIn("price", result[0])
        self.assertNotIn("stock", result[0])

    def test_b2b_reply_contains_business_contact_without_price_claim(self):
        answer = chat_pipeline._format_b2b_large_order_reply("Tôi cần 5 tấn phân cho hợp tác xã", {}, "")
        self.assertIn("0981 205 448", answer)
        self.assertIn("Trưởng phòng Kinh doanh", answer)
        self.assertNotIn("chiết khấu rất tốt", answer)

    def test_catalog_reply_does_not_expose_internal_verification_note(self):
        source = Path(chat_pipeline.__file__).read_text(encoding="utf-8")
        self.assertNotIn("Mình chỉ hiển thị tên/mã sản phẩm", source)

    def test_stale_order_reply_explains_refresh_without_internal_error_code(self):
        answer, reason = chat_pipeline._format_order_lookup_reply({
            "outcome": "unavailable",
            "reason": "ORDER_CACHE_STALE",
        })
        self.assertEqual(reason, "ORDER_CACHE_STALE")
        self.assertIn("quá thời điểm cập nhật", answer)
        self.assertNotIn("ORDER_CACHE_STALE", answer)


if __name__ == "__main__":
    unittest.main()
