import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.config import AmisConfig  # noqa: E402
from domains.amis.projection import assert_public_projection_safe  # noqa: E402
from domains.amis.service import AmisSyncSafetyError, sync_public_snapshots  # noqa: E402


NOW = datetime(2026, 8, 26, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self, datasets):
        self.datasets = datasets

    async def fetch_public_source_datasets(self):
        return self.datasets


class FakePipeline:
    def __init__(self):
        self.commands = []
        self.executed = False

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    def geoadd(self, key, values):
        self.commands.append(("geoadd", key, values))
        return self

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))
        return self

    async def execute(self):
        self.executed = True
        return [True] * len(self.commands)


class FakeRedis:
    def __init__(self):
        self.last_pipeline = None

    def pipeline(self, transaction=True):
        self.last_pipeline = FakePipeline()
        self.last_pipeline.transaction = transaction
        return self.last_pipeline


def datasets(approved=True):
    return {
        "products": [
            {
                "product_code": "CFC-001",
                "product_name": "NPK Cò Bay",
                "brand": "CFC",
                "unit_price": 123456,
                "inactive": False,
            }
        ],
        "customers": [
            {
                "account_number": "KH001",
                "account_name": "Điểm bán mẫu",
                "chatbot_public": approved,
                "chatbot_public_address": "Ô Môn, Cần Thơ",
                "chatbot_public_phone": "0292 000 0000",
                "number_orders": 1,
                "shipping_long": "105.6235",
                "shipping_lat": "10.1092",
                "inactive": False,
            }
        ],
        "loyalty_customers": [
            {
                "account_number": "KH001",
                "account_name": "Điểm bán mẫu",
                "office_tel": "0976000085",
                "total_score": 0,
            }
        ],
        "sale_orders": [
            {
                "account_code": "KH001",
                "phone": "0976000085",
                "sale_order_no": "DH-TEST-001",
                "is_invoiced": True,
                "invoiced_amount": 500000,
                "revenue_status": "Đã ghi",
                "status": "Hoàn thành",
                "sale_order_date": "2026-08-01",
                "sale_order_product_mappings": [
                    {"product_code": "CFC-001", "price": 500000}
                ],
            }
        ],
    }


class AmisSyncServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = AmisConfig(
            public_approval_field="chatbot_public",
            public_phone_field="chatbot_public_phone",
            public_address_field="chatbot_public_address",
            public_recency_days=365,
            allowed_revenue_statuses=("Đã ghi",),
            min_public_products=1,
            min_public_locations=1,
            min_order_lookup_records=1,
            order_lookup_hmac_secret="unit-test-order-hmac",
            min_loyalty_lookup_records=1,
            loyalty_lookup_hmac_secret="unit-test-loyalty-hmac",
        )

    async def test_dry_run_returns_aggregate_only_and_does_not_write(self):
        result = await sync_public_snapshots(
            dry_run=True,
            config=self.config,
            client=FakeClient(datasets()),
            now=NOW,
        )

        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["written"])
        self.assertEqual(result["snapshots"]["products"]["record_count"], 1)
        self.assertEqual(result["snapshots"]["locations"]["record_count"], 1)
        self.assertEqual(result["snapshots"]["order_lookup"]["record_count"], 1)
        self.assertEqual(result["snapshots"]["loyalty_lookup"]["record_count"], 1)
        self.assertEqual(result["snapshots"]["loyalty_lookup"]["direct_loyalty_count"], 1)
        self.assertNotIn("items", result)

    async def test_real_sync_writes_safe_snapshots_and_geo_in_one_transaction(self):
        redis = FakeRedis()
        result = await sync_public_snapshots(
            dry_run=False,
            config=self.config,
            client=FakeClient(datasets()),
            redis_client=redis,
            now=NOW,
        )

        self.assertTrue(result["written"])
        pipeline = redis.last_pipeline
        self.assertTrue(pipeline.transaction)
        self.assertTrue(pipeline.executed)
        self.assertTrue(any(command[0] == "geoadd" for command in pipeline.commands))
        private_order_payload = None
        for command in pipeline.commands:
            if command[0] != "set":
                continue
            payload = json.loads(command[2])
            if command[1] == self.config.redis_order_lookup_key:
                private_order_payload = payload
                continue
            assert_public_projection_safe(payload)
        self.assertIsNotNone(private_order_payload)
        encoded_private = json.dumps(private_order_payload, ensure_ascii=False)
        self.assertNotIn("0292 000 0000", encoded_private)
        self.assertNotIn("account_name", encoded_private)
        self.assertTrue(any(
            command[0] == "hset" and command[1] == self.config.redis_order_lookup_index_key
            for command in pipeline.commands
        ))
        loyalty_hset = next(
            command for command in pipeline.commands
            if command[0] == "hset" and command[1] == self.config.redis_loyalty_lookup_index_key
        )
        encoded_loyalty = json.dumps(loyalty_hset[2], ensure_ascii=False)
        self.assertNotIn("0976000085", encoded_loyalty)
        self.assertNotIn("Điểm bán mẫu", encoded_loyalty)

    async def test_failed_location_gate_preserves_existing_snapshot(self):
        redis = FakeRedis()
        with self.assertRaises(AmisSyncSafetyError):
            await sync_public_snapshots(
                dry_run=False,
                config=self.config,
                client=FakeClient(datasets(approved=False)),
                redis_client=redis,
                now=NOW,
            )

        self.assertIsNone(redis.last_pipeline)

    async def test_small_order_candidate_keeps_previous_private_order_snapshot(self):
        redis = FakeRedis()
        guarded_config = AmisConfig(
            public_approval_field="chatbot_public",
            public_phone_field="chatbot_public_phone",
            public_address_field="chatbot_public_address",
            public_recency_days=365,
            allowed_revenue_statuses=("Đã ghi",),
            min_public_products=1,
            min_public_locations=1,
            min_order_lookup_records=2,
            order_lookup_hmac_secret="unit-test-order-hmac",
            min_loyalty_lookup_records=1,
            loyalty_lookup_hmac_secret="unit-test-loyalty-hmac",
        )

        result = await sync_public_snapshots(
            dry_run=False,
            config=guarded_config,
            client=FakeClient(datasets()),
            redis_client=redis,
            now=NOW,
        )

        self.assertTrue(result["written"])
        self.assertTrue(result["snapshots"]["order_lookup"]["retained_previous"])
        self.assertEqual(result["snapshots"]["order_lookup"]["candidate_record_count"], 1)
        self.assertFalse(any(
            command[0] == "set" and command[1] == guarded_config.redis_order_lookup_key
            for command in redis.last_pipeline.commands
        ))


if __name__ == "__main__":
    unittest.main()
