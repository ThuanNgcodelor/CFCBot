"""Read and validate customer-facing CFC agronomy facts.

This module is intentionally a composer, not an AI agronomist.  Only facts
with an explicit source locator and an approval basis can be returned.  A
technical protocol/dosage additionally needs a named technical approver.  The
current seed contains one low-risk eligibility fact only; it cannot generate a
formula, dosage, policy, or yield commitment.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import unicodedata
from typing import Any


_DEFAULT_FACTS_PATH = Path(__file__).with_name("approved_facts.json")
_CACHE: tuple[str, float, list[dict[str, Any]], list[str]] | None = None
_FACT_TYPES = {"eligibility", "product_fit", "protocol"}
_DOSAGE_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|lit|ha|hecta|công|cong|bao)\b", re.I)


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "d").lower()
    return re.sub(r"\s+", " ", text).strip()


def _facts_path() -> Path:
    configured = str(os.getenv("AGRONOMY_APPROVED_FACTS_PATH", "")).strip()
    return Path(configured) if configured else _DEFAULT_FACTS_PATH


def _parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def validate_agronomy_fact(raw: Any, *, now: datetime | None = None) -> tuple[dict[str, Any] | None, str]:
    """Validate one record without silently upgrading a draft to customer-safe."""
    if not isinstance(raw, dict):
        return None, "FACT_NOT_OBJECT"
    fact = dict(raw)
    if str(fact.get("brand") or "").lower() != "cfc":
        return None, "FACT_BRAND_INVALID"
    if str(fact.get("fact_type") or "") not in _FACT_TYPES:
        return None, "FACT_TYPE_INVALID"
    for field in ("fact_id", "answer", "source_id", "source_locator", "approval_status", "approved_at"):
        if not str(fact.get(field) or "").strip():
            return None, f"FACT_{field.upper()}_MISSING"
    if str(fact.get("approval_status") or "").lower() != "approved":
        return None, "FACT_NOT_APPROVED"
    if not isinstance(fact.get("crops"), list) or not fact["crops"]:
        return None, "FACT_CROPS_INVALID"
    if not isinstance(fact.get("stages", []), list):
        return None, "FACT_STAGES_INVALID"
    if fact["fact_type"] in {"product_fit", "protocol"} and not str(fact.get("approved_by") or "").strip():
        return None, "FACT_TECHNICAL_APPROVER_MISSING"
    if fact["fact_type"] != "protocol" and _DOSAGE_PATTERN.search(str(fact.get("answer") or "")):
        return None, "FACT_DOSAGE_NOT_ALLOWED"
    valid_until = _parse_time(fact.get("valid_until"))
    if valid_until and valid_until < (now or datetime.now(timezone.utc)):
        return None, "FACT_EXPIRED"
    return fact, "OK"


def _load_approved_facts(*, now: datetime | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    global _CACHE
    path = _facts_path()
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return [], ["FACT_FILE_MISSING"]
    cache_key = str(path.resolve())
    if _CACHE and _CACHE[0] == cache_key and _CACHE[1] == stamp:
        return _CACHE[2], _CACHE[3]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [], ["FACT_FILE_INVALID"]
    candidates = payload.get("facts") if isinstance(payload, dict) else None
    if not isinstance(candidates, list):
        return [], ["FACT_LIST_INVALID"]
    approved: list[dict[str, Any]] = []
    rejected: list[str] = []
    ids: set[str] = set()
    for raw in candidates:
        fact, reason = validate_agronomy_fact(raw, now=now)
        if not fact:
            rejected.append(reason)
            continue
        fact_id = str(fact["fact_id"])
        if fact_id in ids:
            rejected.append("FACT_ID_DUPLICATE")
            continue
        ids.add(fact_id)
        approved.append(fact)
    _CACHE = (cache_key, stamp, approved, rejected)
    return approved, rejected


def resolve_approved_agronomy_fact(
    *,
    crop: str,
    crop_stage: str = "",
    request_kind: str = "eligibility",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return one approved fact only when it matches the exact safe request."""
    if request_kind not in _FACT_TYPES:
        return None
    crop_norm = _normalise(crop)
    stage_norm = _normalise(crop_stage)
    if not crop_norm:
        return None
    facts, _ = _load_approved_facts(now=now)
    candidates: list[tuple[int, dict[str, Any]]] = []
    for fact in facts:
        if fact["fact_type"] != request_kind:
            continue
        crop_matches = {_normalise(value) for value in fact.get("crops", [])}
        if crop_norm not in crop_matches:
            continue
        stages = {_normalise(value) for value in fact.get("stages", []) if _normalise(value)}
        if stages and stage_norm not in stages:
            continue
        candidates.append((2 if stage_norm and stage_norm in stages else 1, fact))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (-item[0], str(item[1]["fact_id"])))
    fact = candidates[0][1]
    return {
        "fact_id": str(fact["fact_id"]),
        "answer": str(fact["answer"]).strip(),
        "source_id": str(fact["source_id"]),
        "source_locator": str(fact["source_locator"]),
        "approval_basis": str(fact.get("approval_basis") or ""),
        "fact_type": str(fact["fact_type"]),
        "approved_at": str(fact["approved_at"]),
    }


def approved_fact_status(*, now: datetime | None = None) -> dict[str, Any]:
    """Aggregate-only diagnostics.  Never returns raw draft content or secrets."""
    facts, rejected = _load_approved_facts(now=now)
    return {
        "status": "ok",
        "approved_count": len(facts),
        "by_type": {kind: sum(1 for fact in facts if fact["fact_type"] == kind) for kind in sorted(_FACT_TYPES)},
        "rejected_count": len(rejected),
        "rejected_reasons": sorted(set(rejected)),
    }
