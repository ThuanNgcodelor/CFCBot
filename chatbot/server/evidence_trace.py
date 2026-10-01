"""PII-safe provider tracing and deterministic answer evidence envelopes."""

from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import re
import time
import uuid
from typing import Any

from grounding_policy import assess_grounding
from runtime_manifest import get_runtime_manifest


_TRACE: ContextVar[list[dict[str, Any]] | None] = ContextVar("phase1_ai_attempts", default=None)
_LAST_COMPLETED_TRACE: dict[str, Any] = {"schema_version": 1, "attempts": [], "success": False}
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?84|0)\d{8,10}(?!\d)")
_EMAIL_RE = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")


def prompt_hash(prompt: str, system_prompt: str = "") -> str:
    value = f"{system_prompt}\n\x00\n{prompt}".encode("utf-8")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def begin_request_trace() -> Token:
    return _TRACE.set([])


def end_request_trace(token: Token) -> None:
    global _LAST_COMPLETED_TRACE
    _LAST_COMPLETED_TRACE = provider_trace()
    _TRACE.reset(token)


def record_provider_attempt(
    *,
    provider: str,
    model: str,
    prompt: str,
    system_prompt: str = "",
    prompt_id: str = "unspecified",
    status: str,
    latency_ms: float,
    reason_code: str = "",
    execution_mode: str = "",
) -> None:
    attempts = _TRACE.get()
    if attempts is None:
        return
    attempts.append({
        "provider": provider,
        "model": model,
        "prompt_id": prompt_id,
        "prompt_hash": prompt_hash(prompt, system_prompt),
        "execution_mode": execution_mode or "unknown",
        "status": status,
        "reason_code": reason_code[:80],
        "latency_ms": round(max(0.0, latency_ms), 2),
    })


def provider_trace() -> dict[str, Any]:
    attempts = deepcopy(_TRACE.get() or [])
    successful = next((item for item in reversed(attempts) if item.get("status") == "success"), None)
    return {
        "schema_version": 1,
        "attempts": attempts,
        "success": bool(successful),
        "provider": str((successful or {}).get("provider") or ""),
        "model": str((successful or {}).get("model") or ""),
        "prompt_id": str((successful or {}).get("prompt_id") or ""),
        "prompt_hash": str((successful or {}).get("prompt_hash") or ""),
    }


def latest_provider_trace() -> dict[str, Any]:
    return deepcopy(_LAST_COMPLETED_TRACE)


def redact_text(value: str, *, limit: int = 360) -> str:
    text = _PHONE_RE.sub("[PHONE]", str(value or ""))
    text = _EMAIL_RE.sub("[EMAIL]", text)
    return text[:limit]


def assess_previous_answer_challenge(answer_trace: Any) -> dict[str, Any]:
    """Resolve a source challenge from the stored Phase-1 ledger only.

    This function intentionally does not retrieve, call a tool or infer a fact.
    It returns an explicit state for the customer-facing policy layer to phrase.
    """
    if not isinstance(answer_trace, dict):
        return {"status": "missing", "answer_id": "", "claim_ids": [], "source_types": []}
    answer_id = str(answer_trace.get("answer_id") or "")
    claims = [item for item in (answer_trace.get("claims") or []) if isinstance(item, dict)]
    evidence = [item for item in (answer_trace.get("evidence") or []) if isinstance(item, dict)]
    source_types = sorted({str(item.get("source_type") or "") for item in evidence if item.get("source_type")})
    claim_ids = [str(item.get("claim_id") or "") for item in claims if item.get("claim_id")]
    if not answer_id or not claims:
        return {"status": "missing", "answer_id": answer_id, "claim_ids": claim_ids, "source_types": source_types}
    now = datetime.now(timezone.utc)
    expired = False
    for item in evidence:
        expires_at = str(item.get("expires_at") or "")
        if not expires_at:
            continue
        try:
            expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            expired = expired or expires <= now
        except ValueError:
            # An unparsable expiry cannot prove freshness.
            expired = True
    statuses = {str(item.get("status") or "unverified") for item in claims}
    if expired:
        status = "stale"
    elif statuses == {"verified"} and evidence and all(
        str(item.get("allowed_audience") or "public") == "public" for item in evidence
    ):
        status = "verified"
    elif "blocked" in statuses:
        status = "blocked"
    else:
        status = "unverified"
    return {
        "status": status,
        "answer_id": answer_id,
        "claim_ids": claim_ids,
        "source_types": source_types,
    }


def _source_type(source_id: str) -> str:
    source = str(source_id or "").casefold()
    if source.startswith("amis:internal:"):
        return "privileged_tool"
    if source.startswith("amis:public:"):
        return "public_tool"
    if "shopee" in source or "catalog" in source:
        return "catalog"
    if any(token in source for token in ("faq", "knowledge", "handbook", "reply_docx")):
        return "faq"
    return ""


def build_answer_trace(
    *,
    answer: str,
    intent: str,
    source_id: str = "",
    fallback_reason: str = "",
    query_plan: dict[str, Any] | None = None,
    source_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Produce one P1 envelope without persisting prompts, raw PII, or provider output as evidence."""
    manifest = get_runtime_manifest()
    answer_id = "ans:" + uuid.uuid4().hex
    source_type = _source_type(source_id)
    evidence: list[dict[str, Any]] = []
    if source_type:
        source_snapshot = source_snapshot or {}
        evidence.append({
            "evidence_id": "ev:" + hashlib.sha256(f"{source_type}|{source_id}".encode()).hexdigest()[:20],
            "source_type": source_type,
            "source_id": source_id,
            "source_version": str(source_snapshot.get("snapshot_hash") or ""),
            "snapshot_hash": str(source_snapshot.get("snapshot_hash") or ""),
            "source_timestamp": str(source_snapshot.get("loaded_at") or source_snapshot.get("synced_at") or ""),
            "expires_at": str(source_snapshot.get("expires_at") or "") or None,
            "allowed_audience": "public",
        })
    grounding = assess_grounding(intent=intent, source_id=source_id, fallback_reason=fallback_reason)
    claim_status = "verified" if evidence and grounding.status == "grounded" else (
        "blocked" if grounding.status == "blocked_unsupported_claim" else "unverified"
    )
    claim = {
        "claim_id": "claim:" + hashlib.sha256(f"{answer_id}|{intent}".encode()).hexdigest()[:20],
        "text": redact_text(answer),
        "evidence_ids": [item["evidence_id"] for item in evidence],
        "status": claim_status,
    }
    return {
        "schema_version": 1,
        "answer_id": answer_id,
        "runtime_manifest_id": manifest["runtime_manifest_id"],
        "query_plan_id": "qp:" + hashlib.sha256(repr(query_plan or {}).encode()).hexdigest()[:20],
        "evidence": evidence,
        "claims": [claim],
        "generator": provider_trace(),
        "decision": {"grounding": grounding.to_dict(), "fallback_reason": fallback_reason},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
