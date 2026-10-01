"""Fact-free dialogue routing decisions built from QueryPlan and state."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from query_understanding import QueryPlan


@dataclass(frozen=True)
class RouteDecision:
    action: str = "legacy"
    tool: str = ""
    intent: str = ""
    reason: str = "LEGACY_ROUTE"
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_affirmation(text: str) -> bool:
    return bool(re.fullmatch(
        r"(ok|oke|okay|da|vang|u|uh|um|uk|duoc|gui|gui di|gui link|gui link di|"
        r"cho minh xin|cho xin|yes|co|dung roi|chinh xac)( nha| nhe| shop)?",
        text.strip(),
    ))


def _semantic_route_decision(
    plan: QueryPlan,
    conversation_plan: dict[str, Any] | None,
) -> RouteDecision | None:
    """Translate an accepted Ollama action into a guarded deterministic route."""
    if not isinstance(conversation_plan, dict):
        return None
    try:
        confidence = float(conversation_plan.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if confidence < 0.85:
        return None

    next_action = str(conversation_plan.get("next_action") or "none").strip().lower()
    tool = str(conversation_plan.get("tool") or "none").strip().lower()
    topic_changed = bool(conversation_plan.get("topic_changed"))
    if next_action == "none" or tool == "none":
        return None

    if (
        plan.brand == "cfc"
        and conversation_plan.get("intent") == "dealer_contact_followup"
        and next_action == "dealer_contact_lookup"
        and tool == "dealer_contact_lookup"
    ):
        return RouteDecision(
            action="tool",
            tool="dealer_contact_lookup",
            intent="dealer_contact_followup",
            reason="OLLAMA_SEMANTIC_DEALER_CONTACT",
            confidence=confidence,
        )

    # A clear operational/privacy route remains the authority unless the customer
    # explicitly changed topic. This prevents a noisy LLM plan from bypassing guards.
    protected_intents = {
        "privacy_sensitive_lookup",
        "company_contact_information",
        "cfc_b2b_large_order_request",
        "cfc_product_complaint_request",
        "cfc_order_status_request",
        "cfc_loyalty_lookup_request",
        "cfc_inventory_request",
        "cfc_dealer_location_request",
    }
    if plan.intent in protected_intents and not topic_changed:
        return None

    if plan.brand == "cfc" and next_action == "purchase_intake" and tool == "purchase_intake":
        return RouteDecision(
            action="tool",
            tool="purchase_intake",
            intent="cfc_purchase_request",
            reason="OLLAMA_SEMANTIC_PURCHASE_INTENT",
            confidence=confidence,
        )

    if plan.brand == "cfc" and next_action == "dealer_lookup" and tool == "sales_location_search":
        return RouteDecision(
            action="tool",
            tool="sales_location_search",
            intent="cfc_dealer_location_request",
            reason="OLLAMA_SEMANTIC_DEALER_LOOKUP",
            confidence=confidence,
        )

    capability_routes = {
        "inventory_lookup": ("cfc_inventory_request", "cfc_inventory_unavailable"),
        "order_status_lookup": ("cfc_order_status_request", "cfc_order_status_unavailable"),
        "wholesale_intake": ("cfc_wholesale_policy_request", "cfc_wholesale_policy_unverified"),
    }
    if plan.brand == "cfc" and next_action in capability_routes and tool == next_action:
        _source_intent, boundary_intent = capability_routes[next_action]
        return RouteDecision(
            action="capability_boundary",
            intent=boundary_intent,
            reason="OLLAMA_SEMANTIC_OPERATIONAL_INTENT",
            confidence=confidence,
        )

    if (
        plan.brand == "cfc"
        and next_action == "loyalty_lookup"
        and tool == "loyalty_lookup"
    ):
        return RouteDecision(
            action="tool",
            tool="loyalty_lookup",
            intent="cfc_loyalty_lookup_request",
            reason="OLLAMA_SEMANTIC_LOYALTY_LOOKUP",
            confidence=confidence,
        )

    if plan.brand == "cfc" and next_action == "complaint_intake" and tool == "complaint_intake":
        return RouteDecision(
            action="tool",
            tool="complaint_sop",
            intent="cfc_product_complaint_request",
            reason="OLLAMA_SEMANTIC_COMPLAINT_INTENT",
            confidence=confidence,
        )

    if plan.brand == "cfc" and next_action == "agronomy_intake" and tool == "agronomy_intake":
        return RouteDecision(
            action="tool",
            tool="faq_by_intent",
            intent="cfc_dosage_usage_review",
            reason="OLLAMA_SEMANTIC_AGRONOMY_INTENT",
            confidence=confidence,
        )
    return None


def build_route_decision(
    plan: QueryPlan,
    conversation_state: dict[str, Any],
    conversation_plan: dict[str, Any] | None = None,
) -> RouteDecision:
    """Choose only a route/tool. Facts remain owned by FAQ/catalog/RAG."""
    pending_action = conversation_state.get("pending_action") or {}
    corrected_brand = (plan.constraints or {}).get("corrected_brand")
    if corrected_brand:
        return RouteDecision(
            action="clarify",
            intent="customer_correction_clarify",
            reason="CORRECTION_REQUIRES_PRODUCT",
            confidence=0.98,
        )

    if (
        pending_action.get("name") == "send_product_link"
        and pending_action.get("status") == "waiting_confirmation"
        and _is_affirmation(plan.normalized_query)
    ):
        return RouteDecision(
            action="tool",
            tool="shopee_product_reference",
            intent="product_link_query",
            reason="PENDING_LINK_CONFIRMED",
            confidence=0.99,
        )

    semantic_route = _semantic_route_decision(plan, conversation_plan)
    if semantic_route:
        return semantic_route

    if plan.needs_context and plan.references.get("ordinal"):
        return RouteDecision(
            action="clarify",
            intent="context_clarification",
            reason="ORDINAL_WITHOUT_OPTIONS",
            confidence=0.99,
        )

    if plan.intent == "cfc_clarification_request":
        return RouteDecision(
            action="clarify",
            intent=plan.intent,
            reason="ACTIVE_GOAL_CLARIFICATION",
            confidence=plan.intent_confidence,
        )

    if plan.intent == "company_contact_information":
        return RouteDecision(
            action="tool",
            tool="faq_by_intent",
            intent=plan.intent,
            reason="GROUNDED_CONTACT_LOOKUP",
            confidence=plan.intent_confidence,
        )

    if plan.intent == "cfc_contact_information_request":
        return RouteDecision(
            action="tool",
            tool="faq_by_intent",
            intent="cfc_contact_information_unavailable",
            reason="CFC_CONTACT_REQUIRES_VERIFIED_SOURCE",
            confidence=plan.intent_confidence,
        )

    if plan.intent == "cfc_dealer_location_request":
        return RouteDecision(
            action="tool",
            tool="faq_by_intent",
            intent=plan.intent,
            reason="DEALER_LOCATION_LOOKUP",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent == "cfc_b2b_large_order_request":
        return RouteDecision(
            action="tool",
            tool="b2b_intake",
            intent=plan.intent,
            reason="B2B_LARGE_ORDER_INTAKE",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent == "cfc_purchase_request":
        return RouteDecision(
            action="tool",
            tool="purchase_intake",
            intent=plan.intent,
            reason="EXPLICIT_PURCHASE_WITH_QUANTITY",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent == "cfc_product_complaint_request":
        return RouteDecision(
            action="tool",
            tool="complaint_sop",
            intent=plan.intent,
            reason="COMPLAINT_SOP_HANDOFF",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent in {
        "cfc_price_unverified",
        "cfc_agronomy_review_request",
    }:
        target_intent = (
            "cfc_dosage_usage_review"
            if plan.intent == "cfc_agronomy_review_request"
            else plan.intent
        )
        return RouteDecision(
            action="tool",
            tool="faq_by_intent",
            intent=target_intent,
            reason="GROUNDED_CFC_FAQ",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent == "cfc_order_status_request":
        return RouteDecision(
            action="tool",
            tool="order_status_lookup",
            intent=plan.intent,
            reason="AMIS_WARM_ORDER_LOOKUP",
            confidence=plan.intent_confidence,
        )

    capability_intents = {
        "cfc_inventory_request": "cfc_inventory_unavailable",
        "cfc_wholesale_policy_request": "cfc_wholesale_policy_unverified",
        "financial_service_unsupported": "financial_service_unsupported",
    }
    if (plan.brand == "cfc" or plan.intent == "financial_service_unsupported") and plan.intent in capability_intents:
        return RouteDecision(
            action="capability_boundary",
            intent=capability_intents[plan.intent],
            reason="OPERATIONAL_TOOL_NOT_CONNECTED",
            confidence=plan.intent_confidence,
        )

    if plan.brand == "cfc" and plan.intent == "cfc_loyalty_lookup_request":
        return RouteDecision(
            action="tool",
            tool="loyalty_lookup",
            intent=plan.intent,
            reason="AMIS_WARM_LOYALTY_LOOKUP",
            confidence=plan.intent_confidence,
        )

    return RouteDecision()
