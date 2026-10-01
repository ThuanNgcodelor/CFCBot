"""
domains.rag_test.routes — FastAPI Router cho Kiểm Thử Semantic Search RAG.
"""

import json
import logging
import time
from typing import Optional
import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/test", tags=["RAG Testing & Evaluation"])


@router.post("/query")
async def test_query_endpoint(query: str = Query(...), brand: str = Query("zeo")):
    """Test 1 câu hỏi qua Semantic Search — xem bot sẽ trả lời gì."""
    from rag_search import semantic_search
    result = await semantic_search(query=query, brand=brand, top_k=5)
    return result


class ChatPipelineDebugRequest(BaseModel):
    brand: str = "zeo"
    sender_id: str = "debug_dashboard"
    text: str
    fb_name: Optional[str] = "Dashboard Debug"
    message_id: Optional[str] = ""
    include_rag: bool = True


def _debug_message_id(req: ChatPipelineDebugRequest) -> str:
    explicit = str(req.message_id or "").strip()
    return explicit or f"dashboard-debug:{uuid.uuid4().hex}"


@router.post("/chat-pipeline")
async def test_chat_pipeline_endpoint(req: ChatPipelineDebugRequest):
    """
    Test đúng luồng chatbot thật: QueryPlan/context/router/Shopee/RAG/guardrail.

    Endpoint này dành cho dashboard debug, không thay thế webhook production.
    """
    from chat_pipeline import (
        ChatPipelineRequest,
        _local_session_cache,
        _load_conversation_state,
        _normalize_vn,
        _resolve_reference,
        _extract_query_entities,
        process_chat_pipeline,
    )
    from query_understanding import build_query_plan
    from rag_search import get_redis, semantic_search

    brand = (req.brand or "zeo").lower()
    sender_id = (req.sender_id or "debug_dashboard").strip() or "debug_dashboard"
    raw_text = (req.text or "").strip()
    start = time.perf_counter()

    session_key = f"{brand}:session:messenger:{sender_id}"
    existing_session = _local_session_cache.get(session_key) or {}
    if not existing_session:
        try:
            redis = await get_redis()
            raw_session = await redis.get(session_key)
            if isinstance(raw_session, (str, bytes)) and raw_session:
                existing_session = json.loads(raw_session)
        except Exception as exc:
            logger.debug("Debug endpoint could not read existing session: %s", exc)

    norm_text = _normalize_vn(raw_text)
    conversation_state = _load_conversation_state(existing_session, brand)
    query_entities = _extract_query_entities(norm_text, brand)
    reference_resolution = _resolve_reference(raw_text, norm_text, conversation_state)
    if reference_resolution.get("resolved") and not query_entities.get("product"):
        query_entities = {
            "product": reference_resolution.get("product", ""),
            "product_intent": reference_resolution.get("product_intent", ""),
            "category": reference_resolution.get("category", ""),
            "matched_entities": [{
                "product": reference_resolution.get("product", ""),
                "product_intent": reference_resolution.get("product_intent", ""),
                "category": reference_resolution.get("category", ""),
            }],
        }

    query_plan = build_query_plan(
        raw_text=raw_text,
        norm_text=norm_text,
        brand=brand,
        query_entities=query_entities,
        reference_resolution=reference_resolution,
        conversation_state=conversation_state,
    ).to_dict()

    pipeline_req = ChatPipelineRequest(
        brand=brand,
        sender_id=sender_id,
        text=raw_text,
        fb_name=req.fb_name or "Dashboard Debug",
        message_id=_debug_message_id(req),
    )
    pipeline_res = await process_chat_pipeline(pipeline_req)

    session_after = _local_session_cache.get(session_key) or {}
    trace_after = session_after.get("last_trace") or {}
    state_after = session_after.get("conversation_state") or {}

    rag_result = None
    if req.include_rag:
        try:
            rag_result = await semantic_search(query=raw_text, brand=brand, top_k=5)
        except Exception as exc:
            rag_result = {"error": str(exc)}

    return {
        "ok": True,
        "mode": "chat_pipeline",
        "brand": brand,
        "sender_id": sender_id,
        "request": {
            "raw_text": raw_text,
            "normalized_text": norm_text,
        },
        "response": pipeline_res.dict(),
        "debug": {
            "query_plan": query_plan,
            "reference_resolution": reference_resolution,
            "query_entities": query_entities,
            "last_trace": trace_after,
            "conversation_state": {
                "active_entities": state_after.get("active_entities", {}),
                "active_flow": state_after.get("active_flow", {}),
                "last_products_shown": state_after.get("last_products_shown", [])[:5],
                "last_source_id": state_after.get("last_source_id", ""),
                "recent_turns_count": len(state_after.get("recent_turns", []) or []),
            },
            "raw_rag": rag_result,
        },
        "latency_ms_total": round((time.perf_counter() - start) * 1000, 2),
    }
