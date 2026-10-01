import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.projection import (  # noqa: E402
    PublicProjectionError,
    assert_public_projection_safe,
    build_public_products,
    build_public_sales_locations,
)


NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


def products():
    return [
        {
            "product_code": "ZEO-001",
            "product_name": "Nước giặt ZeO",
            "brand": "ZeO",
            "product_category": "Nước giặt",
            "usage_unit": "Can",
            "description": "Mô tả công khai",
            "unit_price": 170000,
            "purchased_price": 120000,
            "tax": "10%",
            "inactive": False,
        },
        {
            "product_code": "CFC-001",
            "product_name": "NPK Cò Bay",
            "brand": "Cò Bay",
            "product_category": "Phân bón",
            "usage_unit": "Bao",
            "unit_price": 999999,
            "inactive": False,
        },
    ]


def customer(account_number="KH001", approved=True):
    return {
        "account_number": account_number,
        "account_name": f"Điểm bán {account_number}",
        "chatbot_public": approved,
        "chatbot_public_phone": "0292 000 0000",
        "chatbot_public_address": "Định Môn, Cần Thơ",
        "shipping_province": "Cần Thơ",
        "shipping_district": "Thới Lai",
        "shipping_ward": "Định Môn",
        "shipping_long": "105.6235",
        "shipping_lat": "10.1092",
        # Current public-location contract requires the customer aggregate to
        # confirm at least one order or positive sales in addition to a
        # qualifying order row.
        "number_orders": 1,
        "debt": 5000000,
        "tax_code": "SECRET",
        "inactive": False,
    }


def order(account_number="KH001", product_code="ZEO-001", order_date="2026-08-01"):
    return {
        "account_name": account_number,
        "is_invoiced": True,
        "invoiced_amount": 1000000,
        "revenue_status": "Đã ghi",
        "status": "Hoàn thành",
        "sale_order_date": order_date,
        "sale_order_no": "DH-SECRET",
        "sale_order_product_mappings": [
            {"product_code": product_code, "price": 1000000, "amount": 1}
        ],
    }


class AmisProjectionTests(unittest.TestCase):
    def setUp(self):
        self.config = AmisConfig(
            public_approval_field="chatbot_public",
            public_phone_field="chatbot_public_phone",
            public_address_field="chatbot_public_address",
            public_recency_days=365,
            allowed_revenue_statuses=("Đã ghi",),
        )

    def test_product_projection_strips_every_price_and_financial_field(self):
        items, metrics = build_public_products(products())

        self.assertEqual(metrics["public_count"], 2)
        self.assertEqual(items[0]["brand_scope"], "cfc")
        self.assertEqual(items[1]["brand_scope"], "zeo")
        assert_public_projection_safe(items)
        raw_keys = {key for item in items for key in item}
        self.assertNotIn("unit_price", raw_keys)
        self.assertNotIn("purchased_price", raw_keys)

    def test_projection_rejects_price_hidden_inside_public_text(self):
        with self.assertRaises(PublicProjectionError):
            assert_public_projection_safe({"description": "Giá 170.000đ"})

    def test_location_requires_invoice_public_approval_and_brand_line(self):
        customers = [customer("KH001", approved=True), customer("KH002", approved=False)]
        orders = [order("KH001", "ZEO-001"), order("KH002", "CFC-001")]

        items, metrics = build_public_sales_locations(
            customers,
            orders,
            products(),
            self.config,
            now=NOW,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["display_name"], "Điểm bán KH001")
        self.assertEqual(items[0]["brand_scopes"], ["zeo"])
        self.assertEqual(items[0]["longitude"], 105.6235)
        self.assertNotIn("account_number", items[0])
        self.assertNotIn("sale_order_no", items[0])
        self.assertEqual(metrics["skipped_customer_reasons"]["not_publicly_approved"], 1)
        assert_public_projection_safe(items)

    def test_stale_or_non_invoiced_order_does_not_create_location(self):
        stale = order(order_date="2020-01-01")
        not_invoiced = order()
        not_invoiced["is_invoiced"] = False
        not_invoiced["invoiced_amount"] = 0

        items, metrics = build_public_sales_locations(
            [customer()],
            [stale, not_invoiced],
            products(),
            self.config,
            now=NOW,
        )

        self.assertEqual(items, [])
        self.assertEqual(metrics["skipped_order_reasons"]["stale_order_over_recency_window"], 1)
        self.assertEqual(metrics["skipped_order_reasons"]["zero_amount_or_not_invoiced"], 1)

    def test_customer_without_sales_or_order_aggregate_is_not_published(self):
        candidate = customer()
        candidate["number_orders"] = 0
        candidate["order_sales"] = 0

        items, metrics = build_public_sales_locations(
            [candidate], [order()], products(), self.config, now=NOW,
        )

        self.assertEqual(items, [])
        self.assertEqual(metrics["skipped_customer_reasons"]["zero_sales_or_no_orders"], 1)

    def test_allowlist_can_approve_pilot_record_without_public_field(self):
        config = AmisConfig(
            public_account_allowlist=("KH001",),
            public_recency_days=365,
            allowed_revenue_statuses=("Đã ghi",),
            allow_office_phone_fallback=True,
        )
        candidate = customer(approved=False)
        candidate.pop("chatbot_public_address")
        candidate["shipping_address"] = "Định Môn, Cần Thơ"
        candidate["office_tel"] = "0292 000 0000"

        items, _ = build_public_sales_locations(
            [candidate],
            [order()],
            products(),
            config,
            now=NOW,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["public_phone"], "0292 000 0000")

    def test_pilot_approve_all_approves_when_no_allowlist_or_field_configured(self):
        config = AmisConfig(
            public_approval_field="",
            pilot_approve_all=True,
            allow_office_phone_fallback=True,
        )
        candidate = customer(account_number="KH002", approved=False)
        candidate.pop("chatbot_public")
        candidate["shipping_address"] = "Định Môn, Cần Thơ"
        candidate["office_tel"] = "0292 111 2222"

        items, metrics = build_public_sales_locations(
            [candidate],
            [order(account_number="KH002")],
            products(),
            config,
            now=NOW,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["display_name"], "Điểm bán KH002")

    def test_require_coordinates_skips_locations_without_gps(self):
        config = AmisConfig(
            pilot_approve_all=True,
            require_coordinates=True,
            allow_office_phone_fallback=True,
        )
        no_gps_customer = customer(account_number="KH003", approved=True)
        no_gps_customer["shipping_long"] = ""
        no_gps_customer["shipping_lat"] = None
        no_gps_customer["shipping_address"] = "Định Môn, Cần Thơ"

        items, metrics = build_public_sales_locations(
            [no_gps_customer],
            [order(account_number="KH003")],
            products(),
            config,
            now=NOW,
        )

        self.assertEqual(len(items), 0)
        self.assertEqual(metrics["skipped_customer_reasons"]["missing_coordinates"], 1)


if __name__ == "__main__":
    unittest.main()
