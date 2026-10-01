import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.service import AmisSyncSafetyError  # noqa: E402
from domains.amis.warm_staging import commit_warm_run, stage_warm_chunk  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.hashes = {}
        self.deleted = []

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value
        return True

    async def hget(self, key, field):
        return self.hashes.get(key, {}).get(field)

    async def hset(self, key, mapping):
        self.hashes.setdefault(key, {}).update(mapping)
        return len(mapping)

    async def hgetall(self, key):
        return self.hashes.get(key, {})

    async def expire(self, key, seconds):
        return True

    async def delete(self, *keys):
        self.deleted.extend(keys)
        for key in keys:
            self.values.pop(key, None)
            self.hashes.pop(key, None)
        return len(keys)


class AmisWarmStagingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.config = AmisConfig(
            warm_staging_chunk_max_records=2,
            min_public_products=1,
            min_public_locations=1,
            min_order_lookup_records=1,
            order_lookup_hmac_secret="test-secret",
            min_loyalty_lookup_records=1,
            loyalty_lookup_hmac_secret="test-loyalty-secret",
        )
        self.run_id = "amiswarm-test-run-001"
        self.counts = {"customers": 1, "products": 1, "sale_orders": 3}
        self.chunks = {"customers": 1, "products": 1, "sale_orders": 2}

    async def _stage(self, dataset, index, records):
        return await stage_warm_chunk(
            run_id=self.run_id,
            dataset=dataset,
            chunk_index=index,
            records=records,
            expected_counts=self.counts,
            expected_chunks=self.chunks,
            config=self.config,
            redis_client=self.redis,
        )

    async def test_complete_run_reassembles_then_cleans_only_after_publish(self):
        await self._stage("customers", 0, [{"account_number": "KH001"}])
        await self._stage("products", 0, [{"product_code": "P001"}])
        await self._stage("sale_orders", 0, [{"sale_order_no": "A"}, {"sale_order_no": "B"}])
        await self._stage("sale_orders", 1, [{"sale_order_no": "C"}])

        published = {"status": "ok", "written": True}
        with patch(
            "domains.amis.warm_staging.sync_public_snapshots",
            new=AsyncMock(return_value=published),
        ) as sync:
            result = await commit_warm_run(
                run_id=self.run_id,
                config=self.config,
                redis_client=self.redis,
            )

        self.assertIs(result, published)
        raw = sync.await_args.kwargs["raw_datasets"]
        self.assertEqual([row["sale_order_no"] for row in raw["sale_orders"]], ["A", "B", "C"])
        self.assertIs(sync.await_args.kwargs["redis_client"], self.redis)
        self.assertTrue(self.redis.deleted)
        self.assertFalse(self.redis.values)
        self.assertFalse(self.redis.hashes)

    async def test_incomplete_run_does_not_call_publish_or_delete_staging(self):
        await self._stage("customers", 0, [{"account_number": "KH001"}])
        await self._stage("products", 0, [{"product_code": "P001"}])
        await self._stage("sale_orders", 0, [{"sale_order_no": "A"}, {"sale_order_no": "B"}])

        with patch(
            "domains.amis.warm_staging.sync_public_snapshots",
            new=AsyncMock(),
        ) as sync:
            with self.assertRaisesRegex(AmisSyncSafetyError, "incomplete"):
                await commit_warm_run(
                    run_id=self.run_id,
                    config=self.config,
                    redis_client=self.redis,
                )

        sync.assert_not_awaited()
        self.assertFalse(self.redis.deleted)
        self.assertTrue(self.redis.values)

    async def test_rejects_a_chunk_that_does_not_match_plan(self):
        with self.assertRaisesRegex(AmisSyncSafetyError, "record count"):
            await self._stage("sale_orders", 0, [{"sale_order_no": "A"}])

        self.assertFalse(self.redis.values)
        self.assertFalse(self.redis.hashes)

    async def test_optional_loyalty_customer_dataset_is_reassembled(self):
        self.counts["loyalty_customers"] = 2
        self.chunks["loyalty_customers"] = 1
        await self._stage("customers", 0, [{"account_number": "KH001"}])
        await self._stage(
            "loyalty_customers",
            0,
            [{"id": 1, "office_tel": "0976000085"}, {"id": 2}],
        )
        await self._stage("products", 0, [{"product_code": "P001"}])
        await self._stage("sale_orders", 0, [{"sale_order_no": "A"}, {"sale_order_no": "B"}])
        await self._stage("sale_orders", 1, [{"sale_order_no": "C"}])

        with patch(
            "domains.amis.warm_staging.sync_public_snapshots",
            new=AsyncMock(return_value={"status": "ok", "written": True}),
        ) as sync:
            await commit_warm_run(
                run_id=self.run_id,
                config=self.config,
                redis_client=self.redis,
            )

        loyalty_rows = sync.await_args.kwargs["raw_datasets"]["loyalty_customers"]
        self.assertEqual(len(loyalty_rows), 2)
        self.assertEqual(loyalty_rows[0]["office_tel"], "0976000085")


if __name__ == "__main__":
    unittest.main()
