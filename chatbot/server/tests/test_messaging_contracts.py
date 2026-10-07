import asyncio
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.messaging.config import MessagingConfig
from domains.messaging.contracts import ConversationBundleV1, HandoffActionV1, InboundEventV1, LeadDraftV1, MediaInspectRequest, MemoryFactV1, ResponseOutboxEventV1
from domains.messaging.media import inspect_media
from domains.messaging.repository import MessagingRepository
from domains.messaging.service import MessagingRuntime


def config(root: Path, routes: Path | None = None) -> MessagingConfig:
    return MessagingConfig(
        queue_enabled=False, queue_shadow=True, quiet_ms=500, max_window_ms=1500,
        stream_key="test:inbound", consumer_group="test", consumer_name="worker-test",
        sqlite_path=root / "test.sqlite3", control_key="test-key",
        sales_enabled=False, sales_shadow=True,
        sales_routes_path=routes or root / "routes.json", sales_destinations={},
        triage_destination="triage", telegram_bot_token="", handoff_enabled=True,
        sla_default_minutes=30, media_enabled=False, ocr_enabled=False,
        media_max_bytes=10 * 1024 * 1024, media_allowed_hosts=(),
        memory_facts_enabled=True, lead_require_phone=True)


class MessagingContractTests(unittest.TestCase):
    def test_inbound_contract_rejects_missing_sender(self):
        with self.assertRaises(Exception):
            InboundEventV1(idempotency_key="m1", sender_id="", message_id="m1")

    def test_contract_defaults_are_versioned(self):
        event = InboundEventV1(idempotency_key="m1", sender_id="s1", message_id="m1")
        self.assertEqual(event.schema_version, "inbound.v1")
        self.assertTrue(event.trace_id)


class MessagingRepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = MessagingRepository(Path(self.tmp.name) / "messages.sqlite3")
        await self.repo.initialize()

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_response_outbox_is_idempotent(self):
        event = ResponseOutboxEventV1(trace_id="t1", idempotency_key="bundle:1", bundle_id="b1", brand="cfc", sender_id="s1", payload={"answer": "ok"}, status="shadow")
        self.assertTrue(await self.repo.insert_response(event))
        duplicate = event.model_copy(update={"event_id": "other"})
        self.assertFalse(await self.repo.insert_response(duplicate))

    async def test_lead_without_phone_is_created_then_merged(self):
        lead = LeadDraftV1(lead_id="l1", trace_id="t1", conversation_key="cfc:s1", brand="cfc", sender_id="s1", intent="cfc_purchase_request", need="Tôi muốn mua NPK")
        first = await self.repo.upsert_lead(lead)
        self.assertEqual(first.phone, "")
        second = await self.repo.upsert_lead(LeadDraftV1(lead_id="ignored", trace_id="t2", conversation_key="cfc:s1", brand="cfc", sender_id="s1", phone="0900000000"))
        self.assertEqual(second.lead_id, "l1")
        self.assertEqual(second.version, 2)
        self.assertEqual(second.need, "Tôi muốn mua NPK")

    async def test_handoff_claim_is_atomic_and_idempotent(self):
        lead = LeadDraftV1(lead_id="lead-claim", trace_id="t1", conversation_key="cfc:claim", brand="cfc", sender_id="claim", phone="0900000000")
        await self.repo.upsert_lead(lead)
        action = HandoffActionV1(actor_id="sale-a", reason="nhận lead", idempotency_key="claim-1")
        result = await self.repo.handoff_transition("lead-claim", action, "claimed")
        self.assertEqual(result["status"], "claimed")
        again = await self.repo.handoff_transition("lead-claim", action, "claimed")
        self.assertTrue(again["idempotent"])
        with self.assertRaises(ValueError):
            await self.repo.handoff_transition("lead-claim", HandoffActionV1(actor_id="sale-b", idempotency_key="claim-2"), "claimed")

    async def test_memory_fact_is_scoped_to_sender(self):
        fact = MemoryFactV1(brand="cfc", sender_id="memory-1", fact_type="crop", value="sầu riêng", confirmed=True)
        await self.repo.save_fact(fact)
        self.assertEqual(len(await self.repo.list_facts("cfc", "memory-1")), 1)
        self.assertEqual(await self.repo.list_facts("cfc", "memory-2"), [])


class MessagingRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_media_gate_blocks_private_host_and_shadows_public_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = replace(config(Path(tmp)), media_enabled=True, media_allowed_hosts=("93.184.216.34",))
            private = inspect_media(MediaInspectRequest(source_url="http://127.0.0.1/image.jpg"), cfg)
            self.assertEqual(private.status, "blocked")
            public = inspect_media(MediaInspectRequest(source_url="https://93.184.216.34/image.jpg"), cfg)
            self.assertEqual(public.status, "shadow")

    async def test_sales_message_is_human_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = MessagingRuntime(config(Path(tmp)))
            message = runtime._sales_message({
                "lead_id": "27a7450c-8948-4af2-b225-c49900a4c0ed",
                "fb_name": "",
                "phone": "0900000002",
                "area": "Cần Thơ",
                "need": "Tôi muốn đặt 5 bao NPK Cò Bay",
                "destination_key": "triage",
            })
            self.assertIn("KHÁCH HÀNG MỚI — CFC CÒ BAY", message)
            self.assertIn("CFC-A4C0ED", message)
            self.assertNotIn("27a7450c-8948-4af2-b225-c49900a4c0ed", message)
            self.assertIn('href="tel:0900000002"', message)

    async def test_region_route_and_unknown_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            routes = root / "routes.json"
            routes.write_text(json.dumps({"routes": [{"destination_key": "sales_can_tho", "area_aliases": ["Cần Thơ"]}]}), encoding="utf-8")
            runtime = MessagingRuntime(config(root, routes))
            self.assertEqual(runtime._route("Ninh Kiều, Cần Thơ"), ("sales_can_tho", "high"))
            self.assertEqual(runtime._route(""), ("triage", "low"))

    async def test_four_messages_are_processed_once_in_order_and_shadowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = MessagingRuntime(config(root))
            await runtime.repository.initialize()
            now = datetime.now(timezone.utc)
            events = [InboundEventV1(idempotency_key=f"m{i}", sender_id="s1", message_id=f"m{i}", text=text, platform_timestamp=now)
                      for i, text in enumerate(["Tôi muốn mua", "NPK", "10 bao", "ở Cần Thơ"], 1)]
            bundle = ConversationBundleV1(bundle_id="b1", trace_id="trace", brand="cfc", sender_id="s1", events=list(reversed(events)), opened_at=now, due_at=now, max_due_at=now)
            response = MagicMock()
            response.model_dump.return_value = {"answer": "Đã nhận", "intent": "cfc_purchase_request", "lead_stage": "new", "phone": "", "area": "Cần Thơ"}
            runtime.redis = AsyncMock()
            with patch("domains.messaging.service.process_chat_pipeline", AsyncMock(return_value=response)) as pipeline:
                await runtime._process_bundle(bundle)
            pipeline.assert_awaited_once()
            request = pipeline.await_args.args[0]
            self.assertEqual(request.text, "Tôi muốn mua\nNPK\n10 bao\nở Cần Thơ")
            counts = await runtime.repository.counts()
            self.assertEqual(counts["response_outbox"].get("shadow"), 1)
            self.assertEqual(counts["lead_drafts"].get("draft"), None)
            self.assertEqual(counts["sales_outbox"].get("shadow"), None)

    async def test_phone_is_required_before_lead_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runtime = MessagingRuntime(config(root))
            await runtime.repository.initialize()
            now = datetime.now(timezone.utc)
            bundle = ConversationBundleV1(bundle_id="b-phone", trace_id="trace-phone", brand="cfc", sender_id="s-phone", events=[InboundEventV1(idempotency_key="phone-1", sender_id="s-phone", message_id="phone-1", text="Tôi muốn mua NPK", platform_timestamp=now)], opened_at=now, due_at=now, max_due_at=now)
            response = MagicMock()
            response.model_dump.return_value = {"answer": "Đã nhận", "intent": "cfc_purchase_request", "lead_stage": "new", "phone": "", "area": "Cần Thơ"}
            runtime.redis = AsyncMock()
            with patch("domains.messaging.service.process_chat_pipeline", AsyncMock(return_value=response)):
                await runtime._process_bundle(bundle)
            stored = await runtime.repository.list_rows("response_outbox")
            self.assertIn("cho mình xin số điện thoại", stored[0]["payload"]["answer"].lower())
            self.assertEqual((await runtime.repository.counts())["lead_drafts"], {})


if __name__ == "__main__":
    unittest.main()
