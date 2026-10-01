import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from chat_pipeline import (  # noqa: E402
    _build_next_conversation_state,
    _default_conversation_state,
    _detect_need_choice,
    _normalize_vn,
    _resolve_reference,
)
from shopee_matcher import match_shopee_product_reference, match_specific_product_price  # noqa: E402


class ProductLinkFollowupTests(unittest.TestCase):
    def setUp(self):
        self.product = {
            "item_id": "43672853910",
            "name": "Combo 4 nước giặt Pano 1.8kg",
            "brand": "PANO",
            "category": "Nước giặt",
            "price": "239343",
            "link_shopee": "https://shopee.vn/product/20523065/43672853910",
            "in_stock": True,
        }

    def _state_with_product(self, product=None):
        return _build_next_conversation_state(
            _default_conversation_state("zeo"),
            brand="zeo",
            user_message="Có sản phẩm nào khoảng 200k không?",
            bot_reply="1. **Combo 4 nước giặt Pano 1.8kg** — 239.343đ",
            intent="shopee_budget_filter",
            lead_stage="browsing_catalog",
            query_entities={},
            reference_resolution={},
            products_shown=[product or self.product],
        )

    def test_budget_result_keeps_structured_product_identity_and_url(self):
        state = self._state_with_product()
        remembered = state["last_products_shown"][0]
        self.assertEqual(remembered["product_id"], "43672853910")
        self.assertEqual(remembered["rank"], 1)
        self.assertEqual(remembered["price"], "239343")
        self.assertEqual(remembered["shopee_url"], self.product["link_shopee"])
        self.assertEqual(state["pending_options"][0]["product_id"], "43672853910")

    def test_product_that_reference_resolves_to_structured_product(self):
        state = self._state_with_product()
        raw_text = "xin link sản phẩm đó đi"
        resolved = _resolve_reference(raw_text, _normalize_vn(raw_text), state)
        self.assertTrue(resolved["resolved"])
        self.assertEqual(resolved["product_id"], "43672853910")
        self.assertEqual(resolved["shopee_url"], self.product["link_shopee"])

    def test_reference_matcher_uses_product_id_and_returns_direct_link(self):
        state = self._state_with_product()
        raw_text = "xin link sản phẩm đó đi"
        resolved = _resolve_reference(raw_text, _normalize_vn(raw_text), state)
        with patch("shopee_matcher.load_shopee_catalog", return_value=[self.product]):
            result = match_shopee_product_reference(resolved, brand="zeo")
        self.assertFalse(result["is_general_store"])
        self.assertEqual(result["intent"], "shopee_product_link")
        self.assertEqual(result["shopee_url"], self.product["link_shopee"])
        self.assertIn(self.product["name"], result["suggested_reply"])

    def test_legacy_name_only_memory_can_still_resolve_current_catalog(self):
        legacy_state = _default_conversation_state("zeo")
        legacy_state["last_products_shown"] = [{
            "name": self.product["name"],
            "category": "Nước giặt",
            "intent": "shopee_budget_filter",
        }]
        raw_text = "cho xin link sản phẩm đó"
        resolved = _resolve_reference(raw_text, _normalize_vn(raw_text), legacy_state)
        with patch("shopee_matcher.load_shopee_catalog", return_value=[self.product]):
            result = match_shopee_product_reference(resolved, brand="zeo")
        self.assertEqual(result["product_id"], "43672853910")
        self.assertEqual(result["shopee_url"], self.product["link_shopee"])

    def test_explicit_price_query_does_not_reuse_stale_product_context(self):
        fabric_softener = {
            "item_id": "56612838999",
            "name": "Nước xả vải Nano Clean ZeO Hương hoa trắng xạ hương",
            "brand": "ZeO",
            "category": "Nước xả vải",
            "price": 83200,
            "original_price": 128000,
            "discount": "0.35",
            "keywords": ["nước xả vải", "nano clean", "zeo"],
            "variants": ["ZeO"],
            "link_shopee": "https://shopee.vn/product/20523065/56612838999",
            "in_stock": True,
        }
        context = {
            "active_entities": {"product": self.product["name"], "category": "Nước giặt"},
            "last_products_shown": [self.product],
            "last_bot_reply": self.product["name"],
        }
        with patch("shopee_matcher.load_shopee_catalog", return_value=[self.product, fabric_softener]):
            result = match_specific_product_price("Giá nước xả vải zeo shop ơi", brand="zeo", context=context)

        self.assertIsNotNone(result)
        self.assertIn("Nước xả vải", result["suggested_reply"])
        self.assertIn("56612838999", result["shopee_url"])
        self.assertNotIn("Combo 4 nước giặt", result["suggested_reply"])

    def test_fragrant_laundry_recommendation_is_detected_as_need_choice(self):
        self.assertEqual(
            _detect_need_choice(_normalize_vn("Vậy có biết cái nào giặt đồ nó thơm thơm ko nhỉ")),
            "thom_lau",
        )


if __name__ == "__main__":
    unittest.main()
