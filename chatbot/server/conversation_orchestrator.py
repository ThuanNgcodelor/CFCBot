"""Conversation context and guarded Ollama orchestration helpers.

This module only prepares bounded, redacted context and validates an LLM plan.
It does not read business data and it never generates a customer-facing answer.
"""

from __future__ import annotations

import json
import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from evaluation_safety import external_side_effects_allowed


logger = logging.getLogger(__name__)
_shadow_tasks: set[asyncio.Task] = set()


SUPPORTED_FOLLOWUP_INTENTS = {
    "product_followup",
    "product_price_followup",
    "product_link_followup",
    "product_availability_followup",
    "dealer_followup",
    "dealer_contact_followup",
    "delivery_followup",
    "order_status_followup",
    "loyalty_followup",
    "agronomy_followup",
    "wholesale_followup",
    "purchase_followup",
    "complaint_followup",
    "lead_followup",
    "customer_profile_update",
    "topic_switch",
    "clarification",
    "unknown",
}

ALLOWED_TOOLS = {
    "none",
    "product_lookup",
    "sales_location_search",
    "dealer_contact_lookup",
    "delivery_policy_lookup",
    "inventory_lookup",
    "order_status_lookup",
    "loyalty_lookup",
    "agronomy_intake",
    "wholesale_intake",
    "complaint_intake",
    "lead_status_lookup",
    "purchase_intake",
    "customer_profile_update",
}

SEMANTIC_NEXT_ACTIONS = {
    "none",
    "product_lookup",
    "sales_location_search",
    "dealer_contact_lookup",
    "delivery_policy_lookup",
    "inventory_lookup",
    "order_status_lookup",
    "loyalty_lookup",
    "agronomy_intake",
    "wholesale_intake",
    "complaint_intake",
    "lead_status_lookup",
    "purchase_intake",
    "clarification",
    "topic_switch",
    "customer_profile_update",
}


def _redact(text: Any, limit: int = 700) -> str:
    value = str(text or "")
    value = re.sub(r"(?<!\d)(?:\+?84|0)(?:[\s.()-]*\d){8,10}(?!\d)", "[PHONE]", value)
    value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[EMAIL]", value, flags=re.I)
    return value[:limit]


def _redact_value(value: Any, limit: int = 700) -> Any:
    if isinstance(value, str):
        return _redact(value, limit)
    if isinstance(value, list):
        return [_redact_value(item, limit) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _redact_value(item, limit) for key, item in list(value.items())[:40]}
    return value


def load_orchestrator_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            candidate = raw.get("conversation", {})
            if isinstance(candidate, dict):
                cfg = dict(candidate)
        except Exception:
            cfg = {}

    mode = str(os.getenv("CHAT_CONVERSATION_MODE", cfg.get("orchestrator_mode", "off"))).strip().lower()
    if mode not in {"off", "shadow", "assist", "primary"}:
        mode = "off"
    try:
        confidence = float(os.getenv("CHAT_CONVERSATION_MIN_CONFIDENCE", cfg.get("orchestrator_min_confidence", 0.85)))
    except (TypeError, ValueError):
        confidence = 0.85
    try:
        history_limit = int(os.getenv("CHAT_CONVERSATION_HISTORY_LIMIT", cfg.get("orchestrator_history_limit", 12)))
    except (TypeError, ValueError):
        history_limit = 6
    try:
        timeout_seconds = float(os.getenv("CHAT_CONVERSATION_TIMEOUT_SECONDS", cfg.get("orchestrator_timeout_seconds", 6.0)))
    except (TypeError, ValueError):
        timeout_seconds = 6.0
    return {
        "mode": mode,
        "min_confidence": max(0.5, min(confidence, 0.99)),
        "history_limit": max(2, min(history_limit, 12)),
        "timeout_seconds": max(2.5, min(timeout_seconds, 8.0)),
    }


def build_conversation_messages(
    conversation_state: dict[str, Any],
    current_user_message: str,
    *,
    limit: int = 12,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    turns = conversation_state.get("recent_turns") or []
    if isinstance(turns, list):
        for turn in turns[-max(1, limit):]:
            if not isinstance(turn, dict):
                continue
            user_text = _redact(turn.get("user"), 700).strip()
            bot_text = _redact(turn.get("bot"), 700).strip()
            if user_text:
                messages.append({"role": "user", "content": user_text})
            if bot_text:
                messages.append({"role": "assistant", "content": bot_text})
    current = _redact(current_user_message, 700).strip()
    if current:
        messages.append({"role": "user", "content": current})
    return messages[-((max(1, limit) * 2) + 1):]


def build_conversation_context(
    conversation_state: dict[str, Any],
    deterministic_plan: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    active_entities = conversation_state.get("active_entities") or {}
    return _redact_value({
        "summary": conversation_state.get("conversation_summary", ""),
        "active_goal": conversation_state.get("active_goal", {}),
        "confirmed_slots": conversation_state.get("confirmed_slots", {}),
        "active_entities": active_entities,
        "last_products_shown": conversation_state.get("last_products_shown", [])[:8],
        "last_tool_results": conversation_state.get("last_tool_results", [])[:5],
        "pending_request": conversation_state.get("pending_request", {}),
        "pending_question": conversation_state.get("pending_question", ""),
        "topic_stack": conversation_state.get("topic_stack", [])[-5:],
        "deterministic_plan": deterministic_plan or {},
    })


def should_run_orchestrator(
    mode: str,
    *,
    conversation_state: dict[str, Any],
    normalized_text: str,
    brand: str,
) -> bool:
    if mode not in {"shadow", "assist", "primary"}:
        return False
    if not normalized_text.strip() or brand.lower() not in {"zeo", "cfc"}:
        return False
    if mode in {"shadow", "primary"}:
        return True

    # A first-turn request has no conversation to interpret. Once a session exists,
    # let the semantic planner see every turn instead of maintaining a growing list
    # of follow-up keywords.
    has_context = bool(
        conversation_state.get("recent_turns")
        or conversation_state.get("last_tool_results")
        or conversation_state.get("last_products_shown")
        or conversation_state.get("conversation_summary")
        or (conversation_state.get("active_goal") or {}).get("name")
    )
    # Profile replacement is a guarded action and may legitimately be the first
    # turn, before a conversation context exists.
    if re.search(
        r"(?:\b(doi|thay|cap nhat|sua)\b.{0,24}\b(so|sdt|dien thoai)\b|"
        r"\b(so|sdt|dien thoai)\b.{0,24}\b(doi|thay|cap nhat|sua)\b)",
        normalized_text,
    ):
        return True
    if not has_context:
        return False
    return True


def validate_orchestrator_plan(value: Any) -> Optional[dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    intent = str(value.get("intent", "unknown")).strip().lower()
    if intent not in SUPPORTED_FOLLOWUP_INTENTS:
        intent = "unknown"
    try:
        confidence = float(value.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    tool = str(value.get("tool", "none")).strip().lower()
    if tool not in ALLOWED_TOOLS:
        tool = "none"
    reference = value.get("reference") if isinstance(value.get("reference"), dict) else {}
    entity_ids = reference.get("entity_ids") if isinstance(reference.get("entity_ids"), list) else []
    return {
        "intent": intent,
        "confidence": confidence,
        "is_followup": bool(value.get("is_followup", False)),
        "topic_changed": bool(value.get("topic_changed", False)),
        "reference": {
            "type": str(reference.get("type", "none"))[:40],
            "result_id": str(reference.get("result_id", ""))[:120],
            "entity_ids": [str(item)[:120] for item in entity_ids[:20]],
        },
        "requested_fields": [str(item)[:60] for item in (value.get("requested_fields") or [])[:10]],
        "tool": tool,
        "next_action": str(value.get("next_action", "none")).strip().lower()
        if str(value.get("next_action", "none")).strip().lower() in SEMANTIC_NEXT_ACTIONS
        else "none",
        "topic": str(value.get("topic", ""))[:80],
        "arguments": _redact_value(value.get("arguments") if isinstance(value.get("arguments"), dict) else {}),
        "missing_slots": [str(item)[:60] for item in (value.get("missing_slots") or [])[:10]],
        "reason_code": str(value.get("reason_code", ""))[:120],
    }


def is_safe_assist_plan(plan: Optional[dict[str, Any]], *, min_confidence: float) -> bool:
    if not plan:
        return False
    if float(plan.get("confidence", 0.0)) < min_confidence:
        return False
    next_action = str(plan.get("next_action") or "none")
    if (
        not plan.get("is_followup")
        and plan.get("intent") != "customer_profile_update"
        and next_action not in {"purchase_intake", "clarification", "topic_switch"}
    ):
        return False
    if plan.get("intent") in {"unknown", "clarification", "topic_switch"}:
        return False
    return (
        str(plan.get("tool", "none")) in ALLOWED_TOOLS
        and next_action in SEMANTIC_NEXT_ACTIONS
    )


def latest_tool_result(
    conversation_state: dict[str, Any],
    *,
    tool: str = "",
) -> Optional[dict[str, Any]]:
    results = conversation_state.get("last_tool_results") or []
    if not isinstance(results, list):
        return None
    for result in reversed(results):
        if isinstance(result, dict) and not _tool_result_expired(result) and (not tool or result.get("tool") == tool):
            return result
    return None


def _tool_result_expired(result: dict[str, Any]) -> bool:
    """Reject stale references rather than silently reusing prior public data."""
    expires_at = result.get("expires_at")
    if expires_at in (None, ""):
        return False
    try:
        if isinstance(expires_at, (int, float)):
            return float(expires_at) <= datetime.now(timezone.utc).timestamp()
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


def _dealer_ordinal_indices(text: str) -> list[int]:
    """Return zero-based dealer positions explicitly requested by the user."""
    ordinal_patterns = (
        (0, r"\b(?:so|thu)\s*1\b|\b(?:dai ly|cua hang)\s*1\b|\bthu nhat\b|\bdau tien\b"),
        (1, r"\b(?:so|thu)\s*2\b|\b(?:dai ly|cua hang)\s*2\b|\bva\s*2\b|\bthu hai\b"),
        (2, r"\b(?:so|thu)\s*3\b|\b(?:dai ly|cua hang)\s*3\b|\bva\s*3\b|\bthu ba\b"),
        (3, r"\b(?:so|thu)\s*4\b|\b(?:dai ly|cua hang)\s*4\b|\bva\s*4\b|\bthu tu\b"),
        (4, r"\b(?:so|thu)\s*5\b|\b(?:dai ly|cua hang)\s*5\b|\bva\s*5\b|\bthu nam\b"),
    )
    return [index for index, pattern in ordinal_patterns if re.search(pattern, text)]


def _dealer_ordinal_index(text: str) -> Optional[int]:
    """Return the first zero-based dealer position explicitly requested."""
    indices = _dealer_ordinal_indices(text)
    if indices:
        return indices[0]
    return None


def recover_contextual_followup_plan(
    conversation_state: dict[str, Any],
    normalized_text: str,
) -> Optional[dict[str, Any]]:
    """Recover an obvious public-data follow-up when the local planner is unavailable.

    This is deliberately narrow: it can only point to a result already stored in the
    current session and never creates or changes business data.
    """
    text = str(normalized_text or "").strip().lower()
    if not text:
        return None

    previous_dealers = latest_tool_result(conversation_state, tool="sales_location_search")
    if not previous_dealers or not isinstance(previous_dealers.get("items"), list):
        return None
    if not any(isinstance(item, dict) for item in previous_dealers.get("items", [])):
        return None

    dealer_reference = bool(re.search(r"\b(dai ly|cua hang)\b", text))
    dealer_ordinals = _dealer_ordinal_indices(text) if dealer_reference else []
    dealer_ordinal = dealer_ordinals[0] if dealer_ordinals else None
    asks_contact = bool(re.search(
        r"\b(so dien thoai|sdt|dien thoai|so lien he|lien he|goi cho|contact)\b",
        text,
    )) or bool(dealer_reference and dealer_ordinals and re.search(r"\b(xin|cho|gui|lay|so)\b", text))
    refers_to_previous = bool(re.search(
        r"\b(cac cho|cho do|cho tren|cho ay|dai ly|cua hang|vua roi|o tren|nay|do|the do)\b",
        text,
    ))
    asks_company_contact = bool(re.search(
        r"\b(hotline|tong dai|cong ty|cfc|co bay|shop|admin)\b",
        text,
    ))
    if not asks_contact or asks_company_contact:
        return None
    if not refers_to_previous and dealer_ordinal is None:
        # A contact question without a previous-result reference is not enough to
        # safely select a business entity from memory.
        return None

    return {
        "intent": "dealer_contact_followup",
        "confidence": 0.99,
        "is_followup": True,
        "topic_changed": False,
        "reference": {
            "type": "last_tool_result",
            "result_id": str(previous_dealers.get("result_id") or ""),
            "entity_ids": [],
        },
        "requested_fields": ["public_phone"],
        "tool": "dealer_contact_lookup",
        "next_action": "dealer_contact_lookup",
        "arguments": (
            {"selection": "ordinals", "ordinals": [index + 1 for index in dealer_ordinals]}
            if len(dealer_ordinals) > 1
            else {"selection": "ordinal", "ordinal": dealer_ordinal + 1}
            if dealer_ordinal is not None
            else {"selection": "all"}
        ),
        "missing_slots": [],
        "reason_code": (
            "CONTEXT_RECOVERY_PUBLIC_DEALER_CONTACT_ORDINAL"
            if dealer_ordinal is not None
            else "CONTEXT_RECOVERY_PUBLIC_DEALER_CONTACT"
        ),
    }


def select_tool_result_items(
    tool_result: Optional[dict[str, Any]],
    plan: Optional[dict[str, Any]],
    normalized_text: str = "",
) -> list[dict[str, Any]]:
    """Select only entities already present in a stored public tool result."""
    if not isinstance(tool_result, dict) or _tool_result_expired(tool_result):
        return []
    items = [item for item in (tool_result.get("items") or []) if isinstance(item, dict)]
    if not items:
        return []
    reference = plan.get("reference") if isinstance(plan, dict) else {}
    arguments = plan.get("arguments") if isinstance(plan, dict) else {}
    if isinstance(arguments, dict) and arguments.get("selection") == "ordinals":
        selected_indices: list[int] = []
        for ordinal in arguments.get("ordinals") or []:
            try:
                index = int(ordinal) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(items) and index not in selected_indices:
                selected_indices.append(index)
        return [items[index] for index in selected_indices]
    if isinstance(arguments, dict) and arguments.get("selection") == "ordinal":
        try:
            index = int(arguments.get("ordinal")) - 1
        except (TypeError, ValueError):
            index = -1
        if 0 <= index < len(items):
            return [items[index]]
        return []

    entity_ids = {
        str(item)
        for item in (reference.get("entity_ids") or [])
        if str(item).strip()
    } if isinstance(reference, dict) else set()
    if entity_ids:
        selected = [
            item for item in items
            if entity_ids.intersection({str(item.get(key) or "") for key in ("entity_id", "location_id", "id", "product_id", "item_id")})
        ]
        if selected:
            return selected

    index = _dealer_ordinal_index(str(normalized_text or ""))
    if index is not None and 0 <= index < len(items):
        return [items[index]]
    return items


def _shadow_config() -> dict[str, Any]:
    def _number(name: str, default: float, minimum: float, maximum: float) -> float:
        try:
            return max(minimum, min(float(os.getenv(name, default)), maximum))
        except (TypeError, ValueError):
            return default

    return {
        "sample_rate": _number("CHAT_CONVERSATION_SAMPLE_RATE", 1.0, 0.0, 1.0),
        "max_pending": int(_number("CHAT_CONVERSATION_SHADOW_MAX_PENDING", 2, 1, 8)),
        "retention_seconds": int(_number("CHAT_CONVERSATION_SHADOW_RETENTION_SECONDS", 604800, 3600, 2592000)),
    }


def _sample_selected(sample_key: str, sample_rate: float) -> bool:
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    bucket = int(hashlib.sha256(sample_key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return bucket < sample_rate


async def _collect_conversation_shadow(
    *,
    brand: str,
    sender_id: str,
    message_id: str,
    user_query: str,
    conversation_messages: list[dict[str, str]],
    conversation_context: dict[str, Any],
    deterministic_plan: dict[str, Any],
    retention_seconds: int,
) -> None:
    from ai_engine import plan_conversation_turn_with_ai
    from evaluation_ops import append_shadow_event, build_shadow_event
    from rag_search import get_redis

    started = datetime.now(timezone.utc)
    plan = await plan_conversation_turn_with_ai(
        user_query=user_query,
        brand=brand,
        conversation_messages=conversation_messages,
        conversation_context=conversation_context,
        timeout=2.5,
    )
    redis_client = await get_redis()
    session_key = f"{brand}:session:messenger:{sender_id}"
    actual_route = ""
    actual_status = "session_read_failed"
    trace: dict[str, Any] = {}
    try:
        raw_session = await redis_client.get(session_key)
        if isinstance(raw_session, bytes):
            raw_session = raw_session.decode("utf-8")
        session = json.loads(raw_session) if raw_session else {}
        if isinstance(session, dict) and str(session.get("last_user_message") or "").strip() == user_query.strip():
            actual_route = str(session.get("last_intent") or "")
            trace = session.get("last_trace") if isinstance(session.get("last_trace"), dict) else {}
            actual_status = "captured"
        else:
            actual_status = "superseded_or_not_saved"
    except Exception:
        pass
    observation = build_shadow_event(
        event_type="conversation",
        brand=brand,
        sender_id=sender_id,
        message_id=message_id or f"{sender_id}:{user_query}",
        deterministic_proposal=deterministic_plan,
        semantic_proposal=plan or {},
        actual_route=actual_route,
        actual_status=actual_status,
        trace=trace,
        timing_ms=(datetime.now(timezone.utc) - started).total_seconds() * 1000,
        status="predicted" if plan else "no_prediction",
    )
    await append_shadow_event(
        redis_client, brand=brand, event=observation,
        max_observations=500, retention_seconds=retention_seconds,
    )


def _shadow_task_finished(task: asyncio.Task) -> None:
    _shadow_tasks.discard(task)
    try:
        task.result()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.debug("Conversation orchestrator shadow failed: %s", exc)


def schedule_conversation_shadow(
    *,
    brand: str,
    sender_id: str,
    message_id: str,
    user_query: str,
    conversation_messages: list[dict[str, str]],
    conversation_context: dict[str, Any],
    deterministic_plan: dict[str, Any],
) -> str:
    """Run the new planner in the background; it cannot affect the response."""
    if not external_side_effects_allowed():
        return "blocked_evaluation"
    cfg = _shadow_config()
    sample_key = message_id or f"{brand}:{sender_id}:{user_query}"
    if not _sample_selected(sample_key, cfg["sample_rate"]):
        return "not_sampled"
    if len(_shadow_tasks) >= cfg["max_pending"]:
        return "queue_full"
    task = asyncio.create_task(_collect_conversation_shadow(
        brand=brand,
        sender_id=sender_id,
        message_id=message_id,
        user_query=user_query,
        conversation_messages=conversation_messages,
        conversation_context=conversation_context,
        deterministic_plan=deterministic_plan,
        retention_seconds=cfg["retention_seconds"],
    ))
    _shadow_tasks.add(task)
    task.add_done_callback(_shadow_task_finished)
    return "scheduled"


async def drain_conversation_shadow_tasks() -> None:
    tasks = list(_shadow_tasks)
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


def referenced_product_from_plan(
    conversation_state: dict[str, Any],
    plan: Optional[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Resolve a planner reference only against products already shown to the customer."""
    if not plan or not plan.get("is_followup"):
        return None
    if not str(plan.get("intent", "")).startswith("product_"):
        return None
    products = [item for item in (conversation_state.get("last_products_shown") or []) if isinstance(item, dict)]
    if not products:
        return None
    ids = set(plan.get("reference", {}).get("entity_ids", []))
    if ids:
        for item in products:
            item_ids = {
                str(item.get(key) or "")
                for key in ("product_id", "item_id", "id")
            }
            if ids.intersection(item_ids):
                return item
    if len(products) == 1:
        return products[0]
    return None
