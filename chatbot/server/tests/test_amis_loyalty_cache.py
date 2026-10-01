import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.loyalty_cache import (  # noqa: E402
    build_loyalty_lookup_index,
    build_loyalty_lookup_snapshot,
    lookup_cached_loyalty_info,
)


NOW = datetime(2026, 8, 31, 2, 0, tzinfo=timezone.utc)


class FakeRedis:
    def __init__(self, metadata=None, index=None):
        self.metadata = metadata
        self.index = index or {}

    async def get(self, key):
        return self.metadata

    async def hget(self, key, field):
        return self.index.get(field)


class AmisLoyaltyCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = AmisConfig(
            loyalty_lookup_hmac_secret="unit-test-loyalty-secret",
            loyalty_lookup_max_age_seconds=5400,
            min_loyalty_lookup_records=1,
        )

    def _snapshot(self, customers, orders=None, synced_at=None):
        return build_loyalty_lookup_snapshot(
            {"customers": customers, "sale_orders": orders or []},
            config=self.config,
            synced_at=synced_at or NOW.isoformat(),
        )

    async def _lookup(self, snapshot, phone, now=NOW):
        metadata = json.dumps({
            "synced_at": snapshot["synced_at"],
            "record_count": snapshot["record_count"],
        })
        redis = FakeRedis(metadata=metadata, index=build_loyalty_lookup_index(snapshot))
        return await lookup_cached_loyalty_info(
            redis, config=self.config, phone=phone, now=now
        )

    async def test_zero_points_is_a_verified_found_result_and_phone_is_not_persisted(self):
        snapshot = self._snapshot([{
            "id": 1,
            "account_number": "KH001",
            "office_tel": "0976000085",
            "total_score": 0,
        }])
        encoded = json.dumps(snapshot, ensure_ascii=False)
        self.assertNotIn("0976000085", encoded)
        self.assertNotIn("KH001", encoded)

        result = await self._lookup(snapshot, "0976 000 085")
        self.assertEqual(result["outcome"], "found")
        self.assertEqual(result["points"], 0)

    async def test_order_phone_joins_to_customer_loyalty_by_exact_account_alias(self):
        snapshot = self._snapshot(
            [{"id": 7, "account_number": "KH007", "total_score": 125}],
            [{"account_code": "KH007", "phone": "0976000085"}],
        )
        result = await self._lookup(snapshot, "0976000085")
        self.assertEqual(result["outcome"], "found")
        self.assertEqual(result["points"], 125)
        self.assertTrue(result["order_phone_matched"])

    async def test_order_only_phone_reports_profile_without_inventing_points(self):
        snapshot = self._snapshot(
            [],
            [{"account_code": "KH009", "phone": "0976000085"}],
        )
        result = await self._lookup(snapshot, "0976000085")
        self.assertEqual(result["outcome"], "profile_found_no_loyalty")
        self.assertTrue(result["order_phone_matched"])

    async def test_unknown_phone_is_not_found(self):
        snapshot = self._snapshot([{"id": 1, "office_tel": "0976000085"}])
        result = await self._lookup(snapshot, "0388509046")
        self.assertEqual(result["outcome"], "not_found")

    async def test_missing_input_and_cache_failure_fail_closed(self):
        missing = await lookup_cached_loyalty_info(
            FakeRedis(), config=self.config, phone="", now=NOW
        )

        class BrokenRedis:
            async def get(self, _key):
                raise ConnectionError("cache unavailable")

        unavailable = await lookup_cached_loyalty_info(
            BrokenRedis(), config=self.config, phone="0976000085", now=NOW
        )
        self.assertEqual(missing["outcome"], "missing_input")
        self.assertEqual(unavailable, {"outcome": "unavailable", "reason": "LOYALTY_CACHE_READ_FAILED"})

    async def test_stale_snapshot_is_unavailable_not_not_found(self):
        old = NOW - timedelta(hours=2)
        snapshot = self._snapshot(
            [{"id": 1, "office_tel": "0976000085"}], synced_at=old.isoformat()
        )
        result = await self._lookup(snapshot, "0976000085")
        self.assertEqual(result["outcome"], "unavailable")
        self.assertEqual(result["reason"], "LOYALTY_CACHE_STALE")

    async def test_shared_phone_across_accounts_requires_identity_review(self):
        snapshot = self._snapshot([
            {"id": 1, "account_number": "KH001", "office_tel": "0976000085", "total_score": 5},
            {"id": 2, "account_number": "KH002", "office_tel": "0976000085", "total_score": 9},
        ])
        result = await self._lookup(snapshot, "0976000085")
        self.assertEqual(result["outcome"], "ambiguous")


if __name__ == "__main__":
    unittest.main()
