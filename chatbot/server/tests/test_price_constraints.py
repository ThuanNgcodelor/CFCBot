import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from shopee_matcher import (  # noqa: E402
    PriceOperator,
    is_budget_inquiry,
    is_price_extreme_inquiry,
    match_price_extreme,
    match_products_by_budget,
    parse_price_constraint,
)


class PriceConstraintParserTests(unittest.TestCase):
    def assert_constraint(self, query, operator, *, target=None, minimum=None, maximum=None):
        constraint = parse_price_constraint(query)
        self.assertIsNotNone(constraint, query)
        self.assertEqual(constraint.operator, operator, query)
        self.assertEqual(constraint.target, target, query)
        self.assertEqual(constraint.min_value, minimum, query)
        self.assertEqual(constraint.max_value, maximum, query)
        self.assertTrue(is_budget_inquiry(query), query)
        return constraint

    def test_comparator_semantics(self):
        lt = self.assert_constraint("dưới 200k", PriceOperator.LT, maximum=200_000)
        lte = self.assert_constraint("không quá 200 nghìn", PriceOperator.LTE, maximum=200_000)
        gt = self.assert_constraint("trên 200k", PriceOperator.GT, minimum=200_000)
        gte = self.assert_constraint("từ 200k trở lên", PriceOperator.GTE, minimum=200_000)

        self.assertFalse(lt.matches(200_000))
        self.assertTrue(lte.matches(200_000))
        self.assertFalse(gt.matches(200_000))
        self.assertTrue(gte.matches(200_000))

    def test_approx_variants_share_canonical_bounds(self):
        for query in ["khoảng 200k", "tầm 200 nghìn", "quanh 200k", "gần 200k", "xấp xỉ 200k", "cỡ 200k", "~200k"]:
            with self.subTest(query=query):
                self.assert_constraint(
                    query,
                    PriceOperator.APPROX,
                    target=200_000,
                    minimum=170_000,
                    maximum=230_000,
                )

    def test_between_exact_and_units(self):
        self.assert_constraint("150k-250k", PriceOperator.BETWEEN, minimum=150_000, maximum=250_000)
        self.assert_constraint("từ 250 nghìn đến 150 nghìn", PriceOperator.BETWEEN, minimum=150_000, maximum=250_000)
        self.assert_constraint("giá đúng 200.000đ", PriceOperator.EXACT, target=200_000, minimum=200_000, maximum=200_000)
        self.assert_constraint("khoảng 0.2 triệu", PriceOperator.APPROX, target=200_000, minimum=170_000, maximum=230_000)

    def test_product_measurements_are_not_money(self):
        self.assertIsNone(parse_price_constraint("can 3.8kg giá bao nhiêu"))
        self.assertIsNone(parse_price_constraint("gói 400g giá sao"))
        self.assertIsNone(parse_price_constraint("cái số 2 dùng ổn không"))
        self.assert_constraint("có sản phẩm 200k không", PriceOperator.EXACT, target=200_000, minimum=200_000, maximum=200_000)


class ProductBudgetFilterTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"item_id": "P170", "name": "Nước giặt A", "category": "Nước giặt", "price": 170_000, "in_stock": True, "badge": "STANDARD"},
            {"item_id": "P199", "name": "Nước giặt B", "category": "Nước giặt", "price": 199_000, "in_stock": True, "badge": "STANDARD"},
            {"item_id": "P200", "name": "Nước giặt C", "category": "Nước giặt", "price": 200_000, "in_stock": True, "badge": "BEST_SELLER"},
            {"item_id": "P230", "name": "Nước giặt D", "category": "Nước giặt", "price": 230_000, "in_stock": True, "badge": "STANDARD"},
            {"item_id": "D050", "name": "Nước rửa chén E", "category": "Nước rửa chén", "price": 50_000, "in_stock": True, "badge": "STANDARD"},
            {"item_id": "OLD", "name": "Nước giặt hết hàng", "category": "Nước giặt", "price": 190_000, "in_stock": False, "badge": "STANDARD"},
        ]

    def search(self, query, catalog=None):
        with patch("shopee_matcher.load_shopee_catalog", return_value=catalog or self.catalog):
            return match_products_by_budget(query, brand="zeo")

    def test_strict_and_inclusive_boundaries(self):
        below = self.search("nước giặt dưới 200k")
        below_ids = {p["item_id"] for p in below["selected_products"]}
        self.assertNotIn("P200", below_ids)

        at_most = self.search("nước giặt không quá 200k")
        at_most_ids = {p["item_id"] for p in at_most["selected_products"]}
        self.assertIn("P200", at_most_ids)

    def test_approx_is_ranked_by_price_distance(self):
        result = self.search("nước giặt khoảng 200k")
        self.assertEqual(result["price_constraint"]["operator"], "APPROX")
        self.assertEqual(result["selected_products"][0]["item_id"], "P200")
        self.assertFalse(result["range_widened"])

    def test_category_is_a_hard_constraint(self):
        result = self.search("nước giặt dưới 100k")
        self.assertTrue(result["no_results"])
        self.assertEqual(result["intent"], "shopee_budget_filter_no_result")
        self.assertEqual(result["selected_products"], [])
        self.assertNotIn("Nước rửa chén E", result["suggested_reply"])

    def test_approx_expands_once_to_twenty_five_percent(self):
        catalog = [
            {"item_id": "P245", "name": "Nước giặt gần nhất", "category": "Nước giặt", "price": 245_000, "in_stock": True, "badge": "STANDARD"},
        ]
        result = self.search("nước giặt khoảng 200k", catalog=catalog)
        self.assertTrue(result["range_widened"])
        self.assertEqual(result["selected_products"][0]["item_id"], "P245")


class PriceExtremeTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"item_id": "LOW", "name": "Gói dùng thử", "brand": "ZeO", "category": "Nước xả vải", "price": 17_100, "in_stock": True, "link_shopee": "https://shopee.vn/low"},
            {"item_id": "MID", "name": "Combo đang xem", "brand": "PANO", "category": "Nước giặt", "price": 147_582, "in_stock": True, "link_shopee": "https://shopee.vn/mid"},
            {"item_id": "MAX", "name": "Thùng nước giặt Pano Active 6 túi", "brand": "PANO", "category": "Nước giặt", "price": 681_812, "in_stock": True, "link_shopee": "https://shopee.vn/max"},
            {"item_id": "OLD_MAX", "name": "Hết hàng mắc nhất", "brand": "PANO", "category": "Nước giặt", "price": 900_000, "in_stock": False, "link_shopee": "https://shopee.vn/old-max"},
        ]

    def test_detects_highest_price_queries(self):
        self.assertTrue(is_price_extreme_inquiry("sản phẩm nào mắc nhất nhỉ"))
        self.assertTrue(is_price_extreme_inquiry("giá cái nào đắt nhất"))
        self.assertTrue(is_price_extreme_inquiry("giá cao nhất là sản phẩm nào"))

    def test_highest_price_uses_catalog_not_stale_context(self):
        with patch("shopee_matcher.load_shopee_catalog", return_value=self.catalog):
            result = match_price_extreme("giá cái nào mắc nhất", brand="zeo")
        self.assertEqual(result["intent"], "shopee_price_extreme")
        self.assertEqual(result["matched_product"]["item_id"], "MAX")
        self.assertIn("681.812đ", result["suggested_reply"])
        self.assertNotIn("OLD_MAX", [p["item_id"] for p in result["selected_products"]])

    def test_highest_price_respects_category(self):
        with patch("shopee_matcher.load_shopee_catalog", return_value=self.catalog):
            result = match_price_extreme("nước xả vải mắc nhất", brand="zeo")
        self.assertEqual(result["matched_product"]["item_id"], "LOW")
        self.assertIn("Nước xả vải", result["suggested_reply"])


if __name__ == "__main__":
    unittest.main()
