"""HTTP ingress and protected operational views for the messaging domain."""

import hmac
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from .contracts import DeliveryResultV1, EnqueueResponse, HandoffActionV1, InboundEventV1, MediaInspectRequest, MemoryFactV1
from .media import inspect_media
from .service import get_messaging_runtime

router = APIRouter(prefix="/api/messaging", tags=["Messaging Queue"])


def _require_control_key(value: Optional[str]) -> None:
    expected = get_messaging_runtime().config.control_key
    if not expected:
        raise HTTPException(status_code=503, detail="messaging control is not configured")
    if not value or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="invalid messaging control key")


@router.post("/enqueue", response_model=EnqueueResponse, status_code=202)
async def enqueue_event(event: InboundEventV1, x_trace_id: Optional[str] = Header(default=None)):
    if x_trace_id:
        event.trace_id = x_trace_id[:128]
    response = await get_messaging_runtime().enqueue(event)
    if not response.accepted and response.queue_mode == "disabled":
        raise HTTPException(status_code=503, detail="messaging queue is disabled")
    return response


@router.get("/status")
async def messaging_status():
    return await get_messaging_runtime().status()


@router.get("/operations/{collection}")
async def messaging_operations(collection: str, limit: int = Query(50, ge=1, le=200), x_conversation_control_key: Optional[str] = Header(default=None)):
    _require_control_key(x_conversation_control_key)
    table = {"responses": "response_outbox", "leads": "lead_drafts", "sales": "sales_outbox"}.get(collection)
    if not table:
        raise HTTPException(status_code=404, detail="unknown collection")
    return {"items": await get_messaging_runtime().repository.list_rows(table, limit)}


@router.post("/operations/responses/{event_id}/delivery")
async def record_response_delivery(
    event_id: str,
    result: DeliveryResultV1,
    x_conversation_control_key: Optional[str] = Header(default=None),
):
    """Authenticated callback for the future n8n/Meta delivery adapter."""
    _require_control_key(x_conversation_control_key)
    if result.outbox_id != event_id or result.channel != "meta":
        raise HTTPException(status_code=400, detail="delivery result does not match response outbox")
    status = "sent" if result.success else "retry"
    await get_messaging_runtime().repository.mark_delivery(
        "response_outbox", event_id, status,
        external_id=result.external_message_id,
        error=result.error_code,
    )
    return {"ok": True, "event_id": event_id, "status": status}


async def _handoff(lead_id: str, target: str, action: HandoffActionV1, key: Optional[str]):
    _require_control_key(key)
    runtime = get_messaging_runtime()
    if not runtime.config.handoff_enabled:
        raise HTTPException(status_code=503, detail="handoff actions are disabled")
    try:
        return await runtime.repository.handoff_transition(lead_id, action, target)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="lead not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/leads/{lead_id}/claim")
async def claim_lead(lead_id: str, action: HandoffActionV1, x_conversation_control_key: Optional[str] = Header(default=None)):
    return await _handoff(lead_id, "claimed", action, x_conversation_control_key)


@router.post("/leads/{lead_id}/contacted")
async def mark_lead_contacted(lead_id: str, action: HandoffActionV1, x_conversation_control_key: Optional[str] = Header(default=None)):
    return await _handoff(lead_id, "contacted", action, x_conversation_control_key)


@router.post("/leads/{lead_id}/close")
async def close_lead(lead_id: str, action: HandoffActionV1, x_conversation_control_key: Optional[str] = Header(default=None)):
    return await _handoff(lead_id, "closed", action, x_conversation_control_key)


@router.post("/media/inspect")
async def inspect_media_endpoint(req: MediaInspectRequest) :
    return inspect_media(req, get_messaging_runtime().config)


@router.post("/memory/facts")
async def save_memory_fact(fact: MemoryFactV1, x_conversation_control_key: Optional[str] = Header(default=None)):
    _require_control_key(x_conversation_control_key)
    runtime = get_messaging_runtime()
    if not runtime.config.memory_facts_enabled:
        raise HTTPException(status_code=503, detail="memory facts are disabled")
    return await runtime.repository.save_fact(fact)


@router.get("/memory/facts/{brand}/{sender_id}")
async def list_memory_facts(brand: str, sender_id: str, limit: int = Query(50, ge=1, le=100), x_conversation_control_key: Optional[str] = Header(default=None)):
    _require_control_key(x_conversation_control_key)
    runtime = get_messaging_runtime()
    if not runtime.config.memory_facts_enabled:
        raise HTTPException(status_code=503, detail="memory facts are disabled")
    return {"items": await runtime.repository.list_facts(brand, sender_id, limit)}
