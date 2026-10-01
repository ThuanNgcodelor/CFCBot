"""Central, fact-free grounding policy for customer-facing claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


_GENERATOR_SOURCE_PREFIXES = (
    "ollama:",
    "groq:",
    "openrouter:",
    "gemini:",
    "openai:",
    "llm:",
    "ai:",
)


@dataclass(frozen=True)
class GroundingDecision:
    status: str
    claim_type: str
    requires_source: bool
    source_id: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _claim_type(intent: str) -> str:
    value = intent.lower()
    if any(term in value for term in ("contact", "hotline", "address", "website")):
        return "official_contact"
    if "price" in value or "pricing" in value or "budget" in value:
        return "price"
    if "link" in value or "shopee" in value or "online_purchase" in value:
        return "purchase_link"
    if any(term in value for term in ("return", "refund", "warranty", "policy", "claim")):
        return "policy"
    if any(
        term in value
        for term in (
            "dosage",
            "safety",
            "certification",
            "technology",
            "agronomy",
            "agriculture",
            "crop_consultation",
        )
    ):
        return "technical_or_safety"
    if any(term in value for term in ("inventory", "availability", "stock")):
        return "inventory"
    if any(term in value for term in ("order_status", "order_tracking")):
        return "order_status"
    if any(term in value for term in ("loyalty", "points")):
        return "customer_account"
    if "dealer_location" in value:
        return "dealer_directory"
    if any(term in value for term in ("wholesale", "discount")):
        return "commercial_policy"
    return "general"


def is_generator_source(source_id: str) -> bool:
    """Models/providers can generate wording, but they are never business evidence."""
    source = str(source_id or "").strip().casefold()
    return source.startswith(_GENERATOR_SOURCE_PREFIXES)


def assess_grounding(
    *,
    intent: str,
    source_id: str = "",
    fallback_reason: str = "",
) -> GroundingDecision:
    claim_type = _claim_type(intent)
    requires_source = claim_type != "general"
    source = str(source_id or "").strip()
    if source and is_generator_source(source):
        return GroundingDecision(
            "blocked_unsupported_claim",
            claim_type,
            requires_source,
            "",
            "GENERATOR_IS_NOT_EVIDENCE",
        )
    if source:
        return GroundingDecision("grounded", claim_type, requires_source, source, "SOURCE_PRESENT")

    safe_markers = (
        "unverified",
        "clarification",
        "fallback",
        "unavailable",
        "privacy",
        "acknowledgement",
        "greeting",
        "thanks",
        "review",
    )
    if fallback_reason or any(marker in intent.lower() for marker in safe_markers):
        return GroundingDecision("safe_fallback", claim_type, requires_source, "", "NO_UNSUPPORTED_CLAIM")
    if requires_source:
        return GroundingDecision("missing_source", claim_type, True, "", "SOURCE_REQUIRED")
    return GroundingDecision("not_required", claim_type, False, "", "GENERAL_DIALOGUE")
