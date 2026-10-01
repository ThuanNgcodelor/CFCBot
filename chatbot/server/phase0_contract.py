"""Frozen public and persistence contracts for the Phase-0 baseline.

This module contains metadata only.  Runtime code does not route from these
tables, so adding the baseline cannot change a customer answer.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


CONTRACT_SCHEMA_VERSION = 1

CHAT_PIPELINE_REQUEST_FIELDS = (
    "brand",
    "sender_id",
    "text",
    "fb_name",
    "message_id",
    "input_kind",
    "latitude",
    "longitude",
    "attachment_type",
)

CHAT_PIPELINE_RESPONSE_FIELDS = (
    "ok",
    "answer",
    "intent",
    "confidence",
    "score",
    "brand",
    "has_phone",
    "phone",
    "area",
    "lead_stage",
    "shopee_url",
    "fallback_reason",
    "latency_ms",
    "duplicate",
    "idempotency_status",
    "message_id",
    "suppress_send",
    "answer_id",
    "runtime_manifest_id",
)

# Schema v5 is created lazily from the legacy state. ``state_revision`` is
# attached when the session is finalized and persisted.
CONVERSATION_STATE_V5_FIELDS = (
    "schema_version",
    "brand",
    "conversation_topic",
    "current_intent",
    "current_goal",
    "active_entities",
    "last_products_shown",
    "customer_constraints",
    "confirmed_slots",
    "active_goal",
    "active_goal_id",
    "goal_frames",
    "pending_request",
    "pending_requests",
    "last_capability_boundary",
    "active_flow",
    "pending_action",
    "pending_question",
    "pending_slots",
    "pending_options",
    "topic_stack",
    "corrections",
    "takeover_state",
    "covered_fact_ids",
    "last_tool_results",
    "reference_stack",
    "last_answer_reference",
    "recent_turns",
    "conversation_summary",
    "last_source_id",
    "updated_at",
    "state_revision",
)

REDIS_KEY_CONTRACT = {
    "conversation_session": "{brand}:session:messenger:{sender_id}",
    "conversation_history": "{brand}:history:messenger:{sender_id}",
    "customer_profile": "{brand}:customer:messenger:{sender_id}",
    "sender_lease": "{brand}:chat:sender-lock:{sender_id}",
    "message_lease": "{brand}:chat:idempotency:{message_id_sha256}:lease",
    "message_response": "{brand}:chat:idempotency:{message_id_sha256}:response",
    "faq_active": "{brand}:kb:basic:active",
    "faq_candidate": "{brand}:kb:basic:candidate",
    "faq_vector_index": "{brand}:vec:faq",
    "amis_public_products": "amis:public:products:active",
    "amis_public_locations": "amis:public:sales-locations:active",
    "amis_private_orders": "amis:internal:orders:index:active",
    "amis_private_loyalty": "amis:internal:loyalty:index:active",
}

FROZEN_DATASETS = {
    "chatbot/server/eval_conversation_replays.jsonl": {
        "case_count": 19,
        "sha256": "sha256:ad7434c5a2da2efcd8c7a1931811782864584ad108dbb34c301a147dc877faff",
    },
    "chatbot/server/eval_sheet_grounding_cases.jsonl": {
        "case_count": 40,
        "sha256": "sha256:9859bdfea701e576d4702377f1102f74fa37cffec09657da9aab58fc4df6c2e1",
    },
}

# This is the frozen inventory, source boundary, and current risk class. It is
# deliberately descriptive; chat_pipeline remains the source of routing logic.
CAPABILITY_CONTRACTS: dict[str, dict[str, Any]] = {
    "product": {
        "intents": ("cfc_product_catalog_lookup", "product_link_query", "product_price_query"),
        "source_families": ("catalog", "public_tool", "faq"),
        "risk": "public_read",
    },
    "dealer": {
        "intents": ("cfc_dealer_location_request", "cfc_dealer_location_received"),
        "source_families": ("public_tool", "faq"),
        "risk": "public_read",
    },
    "order": {
        "intents": ("cfc_order_status_request", "cfc_order_status_unavailable"),
        "source_families": ("privileged_tool",),
        "risk": "protected_read",
        "required_outcomes": ("found", "missing_input", "not_found_or_forbidden", "stale_or_tool_failure"),
    },
    "loyalty": {
        "intents": ("cfc_loyalty_lookup_request", "cfc_loyalty_unavailable"),
        "source_families": ("privileged_tool",),
        "risk": "protected_read",
        "required_outcomes": ("found", "missing_input", "not_found_or_forbidden", "stale_or_tool_failure"),
    },
    "price_intake": {
        "intents": ("cfc_price_unverified",),
        "source_families": ("capability_boundary",),
        "risk": "intake_only",
    },
    "purchase_intake": {
        "intents": ("cfc_purchase_request",),
        "source_families": ("conversation_state", "faq"),
        "risk": "intake_only",
    },
    "agronomy": {
        "intents": ("cfc_crop_consultation_request", "cfc_dosage_usage_review", "cfc_agronomy_review_request"),
        "source_families": ("approved_fact", "faq", "capability_boundary"),
        "risk": "grounded_advice",
    },
    "contact": {
        "intents": ("cfc_contact_information_request", "company_contact_information"),
        "source_families": ("faq",),
        "risk": "public_read",
    },
    "complaint": {
        "intents": ("cfc_product_complaint_request",),
        "source_families": ("conversation_state", "faq"),
        "risk": "handoff_intake",
    },
    "b2b": {
        "intents": ("cfc_b2b_large_order_request", "cfc_wholesale_policy_request"),
        "source_families": ("faq", "capability_boundary"),
        "risk": "handoff_intake",
    },
    "handoff": {
        "intents": ("human_handoff", "human_handoff_active"),
        "source_families": ("conversation_state",),
        "risk": "operator_control",
    },
    "fallback": {
        "intents": ("fallback_low_confidence", "cfc_grounded_fallback", "cfc_clarification_request"),
        "source_families": ("safe_fallback",),
        "risk": "fail_closed",
    },
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def build_compatibility_manifest() -> dict[str, Any]:
    """Return versioned hashes used by runtime and evaluation reports."""
    contracts = {
        "chat_pipeline_request.v1": CHAT_PIPELINE_REQUEST_FIELDS,
        "chat_pipeline_response.v1": CHAT_PIPELINE_RESPONSE_FIELDS,
        "conversation_state.v5": CONVERSATION_STATE_V5_FIELDS,
        "redis_keys.v1": REDIS_KEY_CONTRACT,
        "capabilities.v1": CAPABILITY_CONTRACTS,
        "datasets.v1": FROZEN_DATASETS,
    }
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "fingerprints": {name: _fingerprint(value) for name, value in contracts.items()},
        "request_fields": list(CHAT_PIPELINE_REQUEST_FIELDS),
        "response_fields": list(CHAT_PIPELINE_RESPONSE_FIELDS),
        "state_fields": list(CONVERSATION_STATE_V5_FIELDS),
        "redis_keys": dict(REDIS_KEY_CONTRACT),
        "capabilities": {name: dict(value) for name, value in CAPABILITY_CONTRACTS.items()},
        "datasets": {name: dict(value) for name, value in FROZEN_DATASETS.items()},
    }
