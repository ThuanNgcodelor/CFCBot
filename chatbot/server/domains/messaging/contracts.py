"""Versioned contracts shared by queue and delivery adapters."""

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MediaDescriptor(BaseModel):
    media_type: Literal["image", "audio", "video", "file", "unknown"] = "unknown"
    attachment_id: str = ""
    mime_type: str = ""
    source_url: str = Field(default="", repr=False)


class InboundEventV1(BaseModel):
    schema_version: Literal["inbound.v1"] = "inbound.v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    idempotency_key: str
    platform: Literal["messenger", "test", "internal"] = "messenger"
    brand: Literal["cfc", "zeo"] = "cfc"
    sender_id: str = Field(min_length=1, max_length=255)
    message_id: str = Field(min_length=1, max_length=255)
    text: str = Field(default="", max_length=12000)
    fb_name: str = Field(default="", max_length=255)
    input_kind: Literal["text", "location", "attachment", "empty"] = "text"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    media: list[MediaDescriptor] = Field(default_factory=list, max_length=10)
    platform_timestamp: datetime = Field(default_factory=utc_now)
    received_at: datetime = Field(default_factory=utc_now)


class ConversationBundleV1(BaseModel):
    schema_version: Literal["bundle.v1"] = "bundle.v1"
    bundle_id: str
    trace_id: str
    brand: Literal["cfc", "zeo"]
    sender_id: str
    events: list[InboundEventV1]
    opened_at: datetime
    due_at: datetime
    max_due_at: datetime


class ResponseOutboxEventV1(BaseModel):
    schema_version: Literal["response-outbox.v1"] = "response-outbox.v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    idempotency_key: str
    bundle_id: str
    brand: str
    sender_id: str
    payload: dict[str, Any]
    status: Literal["pending", "shadow", "sent", "retry", "dead"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)


class LeadDraftV1(BaseModel):
    schema_version: Literal["lead-draft.v1"] = "lead-draft.v1"
    lead_id: str
    version: int = 1
    trace_id: str
    conversation_key: str
    brand: str
    sender_id: str
    fb_name: str = ""
    phone: str = ""
    area: str = ""
    need: str = ""
    intent: str = ""
    destination_key: str = "triage"
    route_confidence: Literal["high", "low"] = "low"
    state: Literal["draft", "routed", "closed"] = "draft"
    updated_at: datetime = Field(default_factory=utc_now)


class SalesOutboxEventV1(BaseModel):
    schema_version: Literal["sales-outbox.v1"] = "sales-outbox.v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    idempotency_key: str
    lead_id: str
    lead_version: int
    destination_key: str
    payload: dict[str, Any]
    status: Literal["pending", "shadow", "sent", "retry", "dead"] = "pending"
    created_at: datetime = Field(default_factory=utc_now)


class DeliveryResultV1(BaseModel):
    schema_version: Literal["delivery-result.v1"] = "delivery-result.v1"
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str
    outbox_id: str
    channel: Literal["meta", "telegram"]
    success: bool
    external_message_id: str = ""
    error_code: str = ""
    occurred_at: datetime = Field(default_factory=utc_now)


class HandoffActionV1(BaseModel):
    actor_id: str = Field(min_length=1, max_length=120)
    reason: str = Field(default="", max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=255)
    sla_minutes: int = Field(default=30, ge=1, le=1440)


class MemoryFactV1(BaseModel):
    schema_version: Literal["memory-fact.v1"] = "memory-fact.v1"
    fact_id: str = Field(default_factory=lambda: str(uuid4()))
    brand: str
    sender_id: str
    fact_type: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    source_event_id: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    identity_scope: str = "conversation"
    confirmed: bool = False
    collected_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = None


class MediaInspectRequest(BaseModel):
    media_type: Literal["image", "audio", "video", "file", "unknown"] = "image"
    source_url: str = Field(min_length=1, max_length=2048, repr=False)
    mime_hint: str = ""
    content_length: Optional[int] = Field(default=None, ge=0)


class MediaInspectResponse(BaseModel):
    accepted: bool
    status: Literal["disabled", "blocked", "shadow", "ready"]
    reason: str = ""
    ocr_text: str = ""
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class EnqueueResponse(BaseModel):
    accepted: bool
    duplicate: bool = False
    event_id: str
    trace_id: str
    queue_mode: Literal["disabled", "shadow", "enabled"]
