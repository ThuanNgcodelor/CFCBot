"""Redis Stream worker, bundle scheduler, outboxes, and LeadDraft routing."""

import asyncio
import hashlib
import html
import json
import logging
import time
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from chat_pipeline import ChatPipelineRequest, process_chat_pipeline
from domains.common.db import get_redis_client
from evaluation_safety import block_external_side_effects
from telegram_notifier import send_telegram_message

from .config import MessagingConfig, load_config
from .contracts import ConversationBundleV1, EnqueueResponse, InboundEventV1, LeadDraftV1, ResponseOutboxEventV1, SalesOutboxEventV1
from .repository import MessagingRepository

logger = logging.getLogger(__name__)

COMMERCIAL_INTENTS = {
    "cfc_purchase_request", "wholesale_dealer", "cfc_wholesale_policy_request",
    "cfc_dealer_location_request", "cfc_dealer_location_received", "wholesale_inquiry",
}


class MessagingRuntime:
    def __init__(self, config: MessagingConfig | None = None):
        self.config = config or load_config()
        self.repository = MessagingRepository(self.config.sqlite_path)
        self.redis = None
        self.tasks: list[asyncio.Task] = []
        self.started = False
        self.metrics = {"accepted": 0, "duplicates": 0, "bundles": 0, "pipeline_errors": 0, "sales_sent": 0, "sales_errors": 0}

    @property
    def due_key(self) -> str:
        return "cfcbot:bundle-due:v1"

    async def start(self) -> None:
        if self.started:
            return
        await self.repository.initialize()
        if self.config.queue_mode != "disabled":
            self.redis = get_redis_client(decode=True)
            try:
                await self.redis.xgroup_create(self.config.stream_key, self.config.consumer_group, id="0", mkstream=True)
            except Exception as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
            self.tasks = [
                asyncio.create_task(self._consume_loop(), name="messaging-consumer"),
                asyncio.create_task(self._finalize_loop(), name="messaging-finalizer"),
            ]
            if self.config.sales_enabled and not self.config.sales_shadow:
                self.tasks.append(asyncio.create_task(self._sales_delivery_loop(), name="sales-delivery"))
        self.started = True
        logger.info("Messaging runtime initialized mode=%s sales_shadow=%s", self.config.queue_mode, self.config.sales_shadow)

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        if self.redis is not None:
            await self.redis.aclose()
        self.tasks, self.redis, self.started = [], None, False

    async def enqueue(self, event: InboundEventV1) -> EnqueueResponse:
        if self.config.queue_mode == "disabled" or self.redis is None:
            return EnqueueResponse(accepted=False, event_id=event.event_id, trace_id=event.trace_id, queue_mode="disabled")
        dedup_key = f"cfcbot:inbound-dedup:v1:{event.idempotency_key}"
        if not await self.redis.set(dedup_key, event.event_id, ex=86400, nx=True):
            self.metrics["duplicates"] += 1
            return EnqueueResponse(accepted=True, duplicate=True, event_id=event.event_id, trace_id=event.trace_id, queue_mode=self.config.queue_mode)
        await self.redis.xadd(self.config.stream_key, {"payload": event.model_dump_json()})
        self.metrics["accepted"] += 1
        return EnqueueResponse(accepted=True, event_id=event.event_id, trace_id=event.trace_id, queue_mode=self.config.queue_mode)

    async def _consume_loop(self) -> None:
        while True:
            try:
                rows = await self.redis.xreadgroup(self.config.consumer_group, self.config.consumer_name, {self.config.stream_key: ">"}, count=20, block=1000)
                for _, messages in rows:
                    for stream_id, fields in messages:
                        try:
                            event = InboundEventV1.model_validate_json(fields["payload"])
                            await self._append_to_bundle(event)
                            await self.redis.xack(self.config.stream_key, self.config.consumer_group, stream_id)
                        except Exception as exc:
                            logger.exception("Inbound event failed stream_id=%s: %s", stream_id, exc)
                            await self.redis.xadd("cfcbot:dead-letter:inbound:v1", {"stream_id": stream_id, "error": str(exc)[:500]})
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Messaging consumer degraded: %s", exc)
                await asyncio.sleep(1)

    async def _append_to_bundle(self, event: InboundEventV1) -> None:
        key = f"cfcbot:bundle:{event.brand}:{event.sender_id}"
        raw = await self.redis.get(key)
        now = datetime.now(timezone.utc)
        if raw:
            bundle = ConversationBundleV1.model_validate_json(raw)
            bundle.events.append(event)
            bundle.events.sort(key=lambda item: (item.platform_timestamp, item.message_id))
            bundle.due_at = min(now + timedelta(milliseconds=self.config.quiet_ms), bundle.max_due_at)
            bundle.trace_id = event.trace_id
        else:
            bundle = ConversationBundleV1(
                bundle_id=str(uuid4()), trace_id=event.trace_id, brand=event.brand, sender_id=event.sender_id,
                events=[event], opened_at=now, due_at=now + timedelta(milliseconds=self.config.quiet_ms),
                max_due_at=now + timedelta(milliseconds=self.config.max_window_ms))
        ttl = max(60, int(self.config.max_window_ms / 1000) + 60)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.set(key, bundle.model_dump_json(), ex=ttl)
            pipe.zadd(self.due_key, {f"{event.brand}:{event.sender_id}": bundle.due_at.timestamp()})
            await pipe.execute()

    async def _finalize_loop(self) -> None:
        while True:
            try:
                await self.finalize_due_once()
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Bundle finalizer degraded: %s", exc)
                await asyncio.sleep(1)

    async def finalize_due_once(self) -> int:
        if self.redis is None:
            return 0
        members = await self.redis.zrangebyscore(self.due_key, "-inf", time.time(), start=0, num=20)
        completed = 0
        for member in members:
            brand, sender_id = member.split(":", 1)
            lease = f"cfcbot:bundle-lease:{brand}:{sender_id}"
            if not await self.redis.set(lease, self.config.consumer_name, nx=True, ex=30):
                continue
            try:
                key = f"cfcbot:bundle:{brand}:{sender_id}"
                raw = await self.redis.get(key)
                if not raw:
                    await self.redis.zrem(self.due_key, member)
                    continue
                bundle = ConversationBundleV1.model_validate_json(raw)
                if bundle.due_at.timestamp() > time.time():
                    await self.redis.zadd(self.due_key, {member: bundle.due_at.timestamp()})
                    continue
                async with self.redis.pipeline(transaction=True) as pipe:
                    pipe.delete(key)
                    pipe.zrem(self.due_key, member)
                    await pipe.execute()
                await self._process_bundle(bundle)
                completed += 1
            finally:
                await self.redis.delete(lease)
        return completed

    async def _process_bundle(self, bundle: ConversationBundleV1) -> None:
        self.metrics["bundles"] += 1
        ordered = sorted(bundle.events, key=lambda item: (item.platform_timestamp, item.message_id))
        texts = [item.text.strip() for item in ordered if item.text.strip()]
        combined_text = "\n".join(texts) if texts else "[Khách gửi nội dung không phải văn bản]"
        last = ordered[-1]
        digest = hashlib.sha256("|".join(item.message_id for item in ordered).encode()).hexdigest()[:24]
        request = ChatPipelineRequest(
            brand=bundle.brand, sender_id=bundle.sender_id, text=combined_text, fb_name=last.fb_name,
            message_id=f"bundle:{digest}", input_kind=last.input_kind, latitude=last.latitude,
            longitude=last.longitude, attachment_type=last.media[0].media_type if last.media else "")
        try:
            guard = block_external_side_effects() if self.config.queue_shadow else nullcontext()
            with guard:
                response = await process_chat_pipeline(request)
            payload = response.model_dump(mode="json")
            payload.update(trace_id=bundle.trace_id, bundle_event_count=len(ordered))
            await self.repository.insert_response(ResponseOutboxEventV1(
                trace_id=bundle.trace_id, idempotency_key=f"bundle:{bundle.bundle_id}:customer-response",
                bundle_id=bundle.bundle_id, brand=bundle.brand, sender_id=bundle.sender_id, payload=payload,
                status="shadow" if self.config.queue_shadow else "pending"))
            await self._capture_lead(bundle, last, combined_text, payload)
        except Exception as exc:
            self.metrics["pipeline_errors"] += 1
            logger.exception("Bundle processing failed bundle_id=%s: %s", bundle.bundle_id, exc)
            await self.redis.xadd("cfcbot:dead-letter:response:v1", {"bundle_id": bundle.bundle_id, "error": str(exc)[:500]})

    def _route(self, area: str) -> tuple[str, str]:
        route_data: dict[str, Any] = {}
        path: Path = self.config.sales_routes_path
        if path.exists():
            try:
                route_data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        normalized = area.casefold().strip()
        for route in route_data.get("routes", []):
            aliases = [str(item).casefold() for item in route.get("area_aliases", [])]
            if normalized and any(alias in normalized for alias in aliases):
                return str(route.get("destination_key") or self.config.triage_destination), "high"
        return self.config.triage_destination, "low"

    async def _capture_lead(self, bundle: ConversationBundleV1, last: InboundEventV1, text: str, payload: dict[str, Any]) -> None:
        intent = str(payload.get("intent") or "")
        if intent not in COMMERCIAL_INTENTS and str(payload.get("lead_stage") or "") not in {"hot", "qualified"}:
            return
        area = str(payload.get("area") or "")
        destination, confidence = self._route(area)
        lead = await self.repository.upsert_lead(LeadDraftV1(
            lead_id=str(uuid4()), trace_id=bundle.trace_id, conversation_key=f"{bundle.brand}:{bundle.sender_id}",
            brand=bundle.brand, sender_id=bundle.sender_id, fb_name=last.fb_name,
            phone=str(payload.get("phone") or ""), area=area, need=text[:1000], intent=intent,
            destination_key=destination, route_confidence=confidence))
        await self.repository.insert_sales(SalesOutboxEventV1(
            trace_id=bundle.trace_id, idempotency_key=f"lead:{lead.lead_id}:v:{lead.version}:sales-handoff",
            lead_id=lead.lead_id, lead_version=lead.version, destination_key=lead.destination_key,
            payload=lead.model_dump(mode="json"),
            status="shadow" if self.config.sales_shadow or not self.config.sales_enabled else "pending"))

    def _sales_message(self, payload: dict[str, Any]) -> str:
        safe = lambda value: html.escape(str(value or "Chưa có"))
        return ("🌾 <b>LEAD CFCBOT</b>\n\n"
                f"🆔 <b>Lead:</b> <code>{safe(payload.get('lead_id'))}</code>\n"
                f"👤 <b>Khách:</b> {safe(payload.get('fb_name'))}\n"
                f"📞 <b>Liên hệ:</b> {safe(payload.get('phone'))}\n"
                f"📍 <b>Khu vực:</b> {safe(payload.get('area'))}\n"
                f"🎯 <b>Nhu cầu:</b> {safe(payload.get('need'))}\n"
                f"🔀 <b>Tuyến:</b> {safe(payload.get('destination_key'))}")

    async def _sales_delivery_loop(self) -> None:
        while True:
            try:
                for row in await self.repository.pending_sales():
                    attempts = int(row.get("attempts") or 0)
                    if attempts >= 5:
                        await self.repository.mark_delivery("sales_outbox", row["event_id"], "dead", error="retry_exhausted")
                        continue
                    try:
                        updated_at = datetime.fromisoformat(str(row.get("updated_at") or "").replace("Z", "+00:00"))
                        if (datetime.now(timezone.utc) - updated_at).total_seconds() < min(300, 2 ** attempts):
                            continue
                    except ValueError:
                        pass
                    chat_id = self.config.sales_destinations.get(row["destination_key"], "")
                    if not self.config.telegram_bot_token or not chat_id:
                        await self.repository.mark_delivery("sales_outbox", row["event_id"], "retry", error="destination_not_configured")
                        continue
                    result = await send_telegram_message(self._sales_message(json.loads(row["payload_json"])), bot_token=self.config.telegram_bot_token, chat_id=chat_id)
                    if result.get("success"):
                        await self.repository.mark_delivery("sales_outbox", row["event_id"], "sent", str(result.get("message_id") or ""))
                        self.metrics["sales_sent"] += 1
                    else:
                        await self.repository.mark_delivery("sales_outbox", row["event_id"], "retry", error=str(result.get("error") or "telegram_error"))
                        self.metrics["sales_errors"] += 1
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Sales delivery degraded: %s", exc)
                await asyncio.sleep(2)

    async def status(self) -> dict[str, Any]:
        result = {"queue_mode": self.config.queue_mode,
                  "sales_mode": "enabled" if self.config.sales_enabled and not self.config.sales_shadow else "shadow",
                  "started": self.started, "metrics": dict(self.metrics), "storage": await self.repository.counts()}
        if self.redis is not None:
            result.update(queue_depth=int(await self.redis.xlen(self.config.stream_key)), bundles_due=int(await self.redis.zcard(self.due_key)))
        return result


_runtime: MessagingRuntime | None = None


def get_messaging_runtime() -> MessagingRuntime:
    global _runtime
    if _runtime is None:
        _runtime = MessagingRuntime()
    return _runtime
