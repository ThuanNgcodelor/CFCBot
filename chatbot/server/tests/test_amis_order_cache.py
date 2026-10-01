import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.order_cache import (  # noqa: E402
    build_order_lookup_index,
    build_order_lookup_snapshot,
    lookup_cached_order_status,
)


NOW = datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc)
ORDER_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60


class FakeRedis:
    def __init__(self, values, hashes=None):
        self.values = values
        self.hashes = hashes or {}

    async def get(self, key):
        return self.values.get(key)

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)


class AmisOrderCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = AmisConfig(
            order_lookup_hmac_secret="unit-test-order-hmac",
            order_lookup_max_age_seconds=ORDER_CACHE_MAX_AGE_SECONDS,
        )
        self.snapshot = build_order_lookup_snapshot(
            {
                "customers": [{
                    "account_number": "KH001",
                    "account_name": "Cửa hàng Minh An",
                    "office_tel": "0901 234 567",
                }],
                "sale_orders": [{
                    "account_code": "KH001",
                "sale_order_no": "DH-2026-889",
                "status": "Đang giao hàng",
                "delivery_status": "Đã giao hàng",
                "sale_order_date": "2026-08-28",
                "deadline_date": "2026-08-30",
                "modified_date": "2026-08-29T07:45:00+00:00",
                }],
                "products": [],
            },
            config=self.config,
            synced_at=NOW.isoformat(),
        )

    def test_snapshot_keeps_only_order_minimum_and_hashes_phone(self):
        encoded = json.dumps(self.snapshot, ensure_ascii=False)
        self.assertEqual(self.snapshot["record_count"], 1)
        self.assertIn("DH-2026-889", encoded)
        self.assertNotIn("0901 234 567", encoded)
        self.assertIn("Cửa hàng Minh An", encoded)
        self.assertNotIn("account_code", encoded)
        self.assertIn("phone_hmacs", encoded)
        self.assertIn("delivery_status", encoded)
        self.assertIn("sale_order_date", encoded)
        self.assertNotIn('"account_name"', encoded)
        self.assertIn('"shop_name"', encoded)

    async def test_exact_order_code_and_matching_phone_returns_status(self):
        redis = FakeRedis({self.config.redis_order_lookup_key: json.dumps(self.snapshot)})
        result = await lookup_cached_order_status(
            redis,
            config=self.config,
            order_code="2026 889",
            phone="+84 901 234 567",
            now=NOW + timedelta(minutes=10),
        )

        self.assertEqual(result["outcome"], "found")
        self.assertEqual(result["order_code"], "DH-2026-889")
        self.assertEqual(result["shop_name"], "Cửa hàng Minh An")
        self.assertEqual(result["status"], "Đang giao hàng")
        self.assertEqual(result["delivery_status"], "Đã giao hàng")
        self.assertEqual(result["sale_order_date"], "2026-08-28")
        self.assertEqual(result["deadline_date"], "2026-08-30")
        self.assertEqual(result["source_id"], "amis:internal:order-warm")
        self.assertEqual(result["data_mode"], "protected_warm_cache")
        self.assertEqual(result["ownership_check"], "order_code_and_phone_hmac_match")
        self.assertTrue(result["freshness_checked"])

    async def test_schema_v2_index_uses_exact_order_key_without_loading_full_snapshot(self):
        index = build_order_lookup_index(self.snapshot)
        metadata = {
            "schema_version": 2,
            "synced_at": NOW.isoformat(),
        }
        redis = FakeRedis(
            {self.config.redis_order_lookup_metadata_key: json.dumps(metadata)},
            {self.config.redis_order_lookup_index_key: index},
        )

        result = await lookup_cached_order_status(
            redis,
            config=self.config,
            order_code="DH-2026-889",
            phone="0901234567",
            now=NOW + timedelta(minutes=10),
        )

        self.assertEqual(result["outcome"], "found")
        self.assertEqual(result["delivery_status"], "Đã giao hàng")
        self.assertEqual(result["sale_order_date"], "2026-08-28")

    async def test_wrong_code_or_phone_does_not_leak_order_information(self):
        redis = FakeRedis({self.config.redis_order_lookup_key: json.dumps(self.snapshot)})
        wrong_code = await lookup_cached_order_status(
            redis, config=self.config, order_code="DH-404", phone="0901234567", now=NOW
        )
        wrong_phone = await lookup_cached_order_status(
            redis, config=self.config, order_code="DH-2026-889", phone="0909999999", now=NOW
        )

        self.assertEqual(wrong_code["outcome"], "not_found")
        self.assertNotIn("status", wrong_code)
        self.assertEqual(wrong_phone["outcome"], "phone_mismatch")
        self.assertNotIn("status", wrong_phone)

    async def test_missing_input_and_cache_failure_fail_closed(self):
        missing = await lookup_cached_order_status(
            FakeRedis({}), config=self.config, order_code="", phone="0901234567", now=NOW
        )

        class BrokenRedis:
            async def get(self, _key):
                raise ConnectionError("cache unavailable")

        unavailable = await lookup_cached_order_status(
            BrokenRedis(), config=self.config, order_code="DH-2026-889", phone="0901234567", now=NOW
        )
        self.assertEqual(missing["outcome"], "missing_input")
        self.assertEqual(unavailable, {"outcome": "unavailable", "reason": "ORDER_CACHE_READ_FAILED"})

    async def test_last_known_good_snapshot_is_usable_for_twelve_hours(self):
        redis = FakeRedis({self.config.redis_order_lookup_key: json.dumps(self.snapshot)})
        result = await lookup_cached_order_status(
            redis,
            config=self.config,
            order_code="DH-2026-889",
            phone="0901234567",
            now=NOW + timedelta(seconds=ORDER_CACHE_MAX_AGE_SECONDS),
        )

        self.assertEqual(result["outcome"], "found")

    async def test_snapshot_older_than_twelve_hours_is_not_used(self):
        redis = FakeRedis({self.config.redis_order_lookup_key: json.dumps(self.snapshot)})
        result = await lookup_cached_order_status(
            redis,
            config=self.config,
            order_code="DH-2026-889",
            phone="0901234567",
            now=NOW + timedelta(seconds=ORDER_CACHE_MAX_AGE_SECONDS + 1),
        )

        self.assertEqual(result["outcome"], "unavailable")
        self.assertEqual(result["reason"], "ORDER_CACHE_STALE")


if __name__ == "__main__":
    unittest.main()
