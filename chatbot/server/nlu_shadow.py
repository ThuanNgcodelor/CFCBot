"""Bounded background collection for the optional LLM NLU shadow planner."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ai_engine import plan_chat_intent_with_ai
from evaluation_ops import append_shadow_event, build_shadow_event
from evaluation_safety import external_side_effects_allowed
from rag_search import get_redis


logger = logging.getLogger(__name__)

_pending_tasks: set[asyncio.Task] = set()


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _shadow_config() -> dict[str, Any]:
    nlu_cfg: dict[str, Any] = {}
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        try:
            raw_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            candidate = raw_cfg.get("llm_nlu", {})
            if isinstance(candidate, dict):
                nlu_cfg = candidate
        except Exception as exc:
            logger.debug("Could not read LLM NLU shadow settings: %s", exc)

    timeout = _safe_float(
        os.getenv("LLM_NLU_SHADOW_TIMEOUT") or nlu_cfg.get("shadow_timeout_seconds"),
        20.0,
    )
    max_pending = _safe_int(
        os.getenv("LLM_NLU_SHADOW_MAX_PENDING") or nlu_cfg.get("shadow_max_pending"),
        2,
    )
    max_observations = _safe_int(nlu_cfg.get("shadow_max_observations"), 500)
    retention_seconds = _safe_int(nlu_cfg.get("shadow_retention_seconds"), 604800)
    sample_rate = _safe_float(
        os.getenv("LLM_NLU_SHADOW_SAMPLE_RATE") or nlu_cfg.get("shadow_sample_rate"),
        1.0,
    )
    return {
        "timeout": max(2.0, min(timeout, 40.0)),
        "max_pending": max(1, min(max_pending, 8)),
        "max_observations": max(50, min(max_observations, 5000)),
        "retention_seconds": max(3600, min(retention_seconds, 2592000)),
        "sample_rate": max(0.0, min(sample_rate, 1.0)),
    }


def _redact_text(text: str, limit: int = 500) -> str:
    value = str(text or "")
    value = re.sub(r"(?<!\d)(?:\+?84|0)(?:[\s.()-]*\d){8,10}(?!\d)", "[PHONE]", value)
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", value, flags=re.I)
    return value[:limit]


def _redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_payload(item) for key, item in value.items()}
    return value


def _stable_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def _sample_selected(sample_key: str, sample_rate: float) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    bucket = int(hashlib.sha256(sample_key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return bucket < sample_rate


def _intent_family(intent: str) -> str:
    value = str(intent or "").strip().lower()
    aliases = {
        "shopee_price_extreme": "price_extreme",
        "shopee_budget_filter": "budget_filter",
        "shopee_product_link": "product_link",
        "specific_product_pricing": "specific_price",
        "return_fee_unverified": "return_fee",
        "customer_privacy_protected": "customer_privacy",
        "contextual_availability_unverified": "product_availability",
        "context_reference_clarify": "clarification",
    }
    if value.startswith("need_consultation"):
        return "need_consultation"
    return aliases.get(value, value)


async def _load_actual_outcome(
    redis_client: Any, session_key: str, expected_query: str,
) -> tuple[str, str, dict[str, Any]]:
    try:
        raw_session = await redis_client.get(session_key)
        if isinstance(raw_session, bytes):
            raw_session = raw_session.decode("utf-8")
        session = json.loads(raw_session) if raw_session else {}
        if not isinstance(session, dict):
            return "", "invalid_session", {}
        if str(session.get("last_user_message", "")).strip() != expected_query.strip():
            return "", "superseded_or_not_saved", {}
        trace = session.get("last_trace") if isinstance(session.get("last_trace"), dict) else {}
        return str(session.get("last_intent", "")).strip(), "captured", trace
    except Exception as exc:
        logger.debug("Could not load actual intent for NLU shadow: %s", exc)
        return "", "session_read_failed", {}


async def collect_nlu_shadow_observation(
    *,
    brand: str,
    sender_id: str,
    message_id: str,
    raw_text: str,
    normalized_text: str,
    conversation_summary: str,
    deterministic_plan: dict[str, Any],
    confidence_threshold: float,
    timeout: float,
    max_observations: int,
    retention_seconds: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    bounded_timeout = max(2.0, min(float(timeout or 20.0), 40.0))
    prediction = await asyncio.wait_for(
        plan_chat_intent_with_ai(
            raw_text, brand=brand, conversation_summary=conversation_summary, timeout=bounded_timeout,
        ),
        timeout=bounded_timeout + 1.0,
    )
    latency_ms = round((time.perf_counter() - started) * 1000, 2)

    redis_client = await get_redis()
    session_key = f"{brand}:session:messenger:{sender_id}"
    actual_intent, actual_status, trace = await _load_actual_outcome(redis_client, session_key, raw_text)
    predicted_intent = str((prediction or {}).get("intent", "")).strip()
    predicted_confidence = _safe_float((prediction or {}).get("confidence"), 0.0)
    actual_family = _intent_family(actual_intent)
    predicted_family = _intent_family(predicted_intent)

    observation = build_shadow_event(
        event_type="nlu",
        brand=brand,
        sender_id=sender_id,
        message_id=message_id or f"{sender_id}:{raw_text}",
        deterministic_proposal=deterministic_plan,
        semantic_proposal=prediction or {},
        actual_route=actual_intent,
        actual_status=actual_status,
        trace=trace,
        timing_ms=latency_ms,
        status="predicted" if prediction else "no_prediction",
    )
    observation.update({
        "agreement": bool(actual_family and predicted_family and actual_family == predicted_family),
        "meets_threshold": predicted_confidence >= confidence_threshold,
    })
    await append_shadow_event(
        redis_client, brand=brand, event=observation,
        max_observations=max_observations, retention_seconds=retention_seconds,
    )
    return observation


def _task_finished(task: asyncio.Task) -> None:
    _pending_tasks.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.warning("LLM NLU shadow observation failed: %s", exc)


def schedule_nlu_shadow(
    *,
    brand: str,
    sender_id: str,
    message_id: str,
    raw_text: str,
    normalized_text: str,
    conversation_summary: str,
    deterministic_plan: dict[str, Any],
    confidence_threshold: float,
) -> str:
    """Schedule one non-blocking shadow observation and return its scheduling status."""
    if not external_side_effects_allowed():
        return "blocked_evaluation"
    cfg = _shadow_config()
    sample_key = message_id or f"{brand}:{sender_id}:{raw_text}"
    if not _sample_selected(sample_key, cfg["sample_rate"]):
        return "not_sampled"
    if len(_pending_tasks) >= cfg["max_pending"]:
        logger.info("Skip LLM NLU shadow: pending queue is full (%d)", len(_pending_tasks))
        return "queue_full"

    task = asyncio.create_task(collect_nlu_shadow_observation(
        brand=brand,
        sender_id=sender_id,
        message_id=message_id,
        raw_text=raw_text,
        normalized_text=normalized_text,
        conversation_summary=conversation_summary,
        deterministic_plan=deterministic_plan,
        confidence_threshold=confidence_threshold,
        timeout=cfg["timeout"],
        max_observations=cfg["max_observations"],
        retention_seconds=cfg["retention_seconds"],
    ))
    _pending_tasks.add(task)
    task.add_done_callback(_task_finished)
    return "scheduled"


async def drain_nlu_shadow_tasks() -> None:
    """Wait for pending observations. Intended for tests and controlled shutdowns."""
    tasks = list(_pending_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
