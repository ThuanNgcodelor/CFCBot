"""Phase-5 primitives for reproducible evaluation and passive canary control.

Nothing in this module changes a customer route.  A production rollout has to
explicitly wire a capability to a positive canary decision after business
approval.  Until then every decision is ``control``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any, Iterable

from runtime_manifest import get_runtime_manifest


EVALUATION_SCHEMA_VERSION = 1
SHADOW_EVENT_SCHEMA_VERSION = 2
CANARY_POLICY_VERSION = "phase5.canary.v1"
_SERVER_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SERVER_DIR.parents[1]
VALIDATION_MODES = frozenset({
    "unit_static",
    "pipeline_fixture",
    "ollama_local",
    "redis_integration",
    "live_canary",
})
_HIGH_RISK_CAPABILITIES = {
    "order_status", "inventory", "price", "discount", "loyalty", "agronomy_protocol",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _source_family(trace: dict[str, Any]) -> str:
    answer_trace = trace.get("answer_trace") if isinstance(trace.get("answer_trace"), dict) else {}
    evidence = answer_trace.get("evidence") if isinstance(answer_trace.get("evidence"), list) else []
    types = sorted({str(item.get("source_type") or "") for item in evidence if isinstance(item, dict)})
    if types:
        return "+".join(item for item in types if item)
    source_id = str(trace.get("source_id") or "").casefold()
    if source_id.startswith("amis:internal:"):
        return "privileged_tool"
    if source_id.startswith("amis:public:"):
        return "public_tool"
    if "shopee" in source_id or "catalog" in source_id:
        return "catalog"
    if any(marker in source_id for marker in ("faq", "knowledge", "handbook", "reply_docx")):
        return "faq"
    return ""


def _claim_statuses(trace: dict[str, Any]) -> list[str]:
    answer_trace = trace.get("answer_trace") if isinstance(trace.get("answer_trace"), dict) else {}
    claims = answer_trace.get("claims") if isinstance(answer_trace.get("claims"), list) else []
    return sorted({str(item.get("status") or "") for item in claims if isinstance(item, dict) and item.get("status")})


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:16]


def build_dataset_manifest(paths: Iterable[Path | str]) -> dict[str, Any]:
    """Pin an eval run to exact JSONL corpus bytes, without copying its text."""
    datasets: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        content = path.read_bytes()
        case_ids: list[str] = []
        for line_number, raw_line in enumerate(content.decode("utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            value = json.loads(line)
            case_id = str(value.get("id") or "") if isinstance(value, dict) else ""
            if not case_id:
                raise ValueError(f"Evaluation dataset missing id at {path}:{line_number}")
            if case_id in seen_case_ids:
                raise ValueError(f"Duplicate evaluation case id: {case_id}")
            seen_case_ids.add(case_id)
            case_ids.append(case_id)
        try:
            display_path = path.resolve().relative_to(_REPO_ROOT.resolve()).as_posix()
        except ValueError:
            display_path = path.name
        datasets.append({
            "path": display_path,
            "sha256": _sha256(content),
            "case_count": len(case_ids),
            "case_id_hash": _sha256(_canonical(sorted(case_ids))),
        })
    payload = {"schema_version": EVALUATION_SCHEMA_VERSION, "datasets": datasets}
    payload["dataset_manifest_id"] = _sha256(_canonical(payload))
    return payload


def evaluation_report_envelope(
    report: dict[str, Any], *, dataset_paths: Iterable[Path | str], validation_mode: str,
) -> dict[str, Any]:
    """Attach reproducibility metadata to an offline/replay report."""
    if validation_mode not in VALIDATION_MODES:
        allowed = ", ".join(sorted(VALIDATION_MODES))
        raise ValueError(f"Unsupported validation_mode={validation_mode!r}; expected one of: {allowed}")
    payload = dict(report)
    payload["schema_version"] = EVALUATION_SCHEMA_VERSION
    payload["validation_mode"] = validation_mode
    payload["runtime_manifest"] = get_runtime_manifest()
    payload["dataset_manifest"] = build_dataset_manifest(dataset_paths)
    report_identity = {
        "schema_version": payload["schema_version"],
        "runtime_manifest_id": payload["runtime_manifest"]["runtime_manifest_id"],
        "dataset_manifest_id": payload["dataset_manifest"]["dataset_manifest_id"],
        "generated_at": payload.get("generated_at", ""),
    }
    payload["report_id"] = "eval:" + _sha256(_canonical(report_identity)).split(":", 1)[1][:24]
    return payload


def build_shadow_event(
    *,
    event_type: str,
    brand: str,
    sender_id: str,
    message_id: str,
    deterministic_proposal: dict[str, Any],
    semantic_proposal: dict[str, Any],
    actual_route: str,
    trace: dict[str, Any],
    status: str,
    timing_ms: float,
    actual_status: str = "",
) -> dict[str, Any]:
    """Return a bounded event with hashes/metadata only, never query or sender text."""
    answer_trace = trace.get("answer_trace") if isinstance(trace.get("answer_trace"), dict) else {}
    generator = answer_trace.get("generator") if isinstance(answer_trace.get("generator"), dict) else {}
    event = {
        "schema_version": SHADOW_EVENT_SCHEMA_VERSION,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "event_type": str(event_type or "unknown"),
        "mode": "shadow",
        "brand": str(brand or "").lower(),
        "turn_hash": _hash_identifier(f"{brand}:{message_id or sender_id}"),
        "sender_hash": _hash_identifier(f"{brand}:{sender_id}"),
        "runtime_manifest_id": str(trace.get("runtime_manifest_id") or answer_trace.get("runtime_manifest_id") or ""),
        "deterministic_proposal": {
            "intent": str(deterministic_proposal.get("intent") or ""),
            "candidate_id": str(deterministic_proposal.get("primary_candidate_id") or ""),
            "needs_context": bool(deterministic_proposal.get("needs_context")),
            "needs_product_tool": bool(deterministic_proposal.get("needs_product_tool")),
        },
        "semantic_proposal": {
            "intent": str(semantic_proposal.get("intent") or ""),
            "confidence": _safe_float(semantic_proposal.get("confidence")),
            "provider": str(semantic_proposal.get("provider") or ""),
            "model": str(semantic_proposal.get("model") or ""),
        },
        "accepted_plan": {
            "intent": str((trace.get("query_plan") or {}).get("intent") or actual_route or ""),
            "query_plan_id": str(answer_trace.get("query_plan_id") or ""),
        },
        "actual_route": str(actual_route or ""),
        "actual_status": str(actual_status or ""),
        "source_family": _source_family(trace),
        "answer_id": str(answer_trace.get("answer_id") or ""),
        "claim_statuses": _claim_statuses(trace),
        "timings": {"shadow_planner_ms": round(max(0.0, timing_ms), 2)},
        "generator": {
            "provider": str(generator.get("provider") or ""),
            "model": str(generator.get("model") or ""),
        },
        "fallback_reason": str(trace.get("fallback_reason") or "")[:120],
        "error_code": "" if status in {"predicted", "no_prediction"} else str(status)[:80],
        "status": str(status or "unknown"),
    }
    return event


async def append_shadow_event(
    redis_client: Any, *, brand: str, event: dict[str, Any], max_observations: int, retention_seconds: int,
) -> None:
    key = f"{str(brand).lower()}:shadow:v2:events"
    await redis_client.rpush(key, json.dumps(event, ensure_ascii=False, separators=(",", ":")))
    await redis_client.ltrim(key, -max(50, int(max_observations)), -1)
    await redis_client.expire(key, max(3600, int(retention_seconds)))


@dataclass(frozen=True)
class CanaryPolicy:
    mode: str
    percentage: int
    capabilities: tuple[str, ...]
    has_salt: bool
    high_risk_allowed: bool
    version: str = CANARY_POLICY_VERSION

    @classmethod
    def from_environment(cls) -> "CanaryPolicy":
        mode = str(os.getenv("CHAT_CANARY_MODE", "off")).strip().lower()
        if mode not in {"off", "shadow", "canary"}:
            mode = "off"
        try:
            percentage = int(os.getenv("CHAT_CANARY_PERCENT", "0"))
        except (TypeError, ValueError):
            percentage = 0
        if percentage not in {0, 5, 25, 100}:
            percentage = 0
        capabilities = tuple(sorted({
            item.strip().lower()
            for item in os.getenv("CHAT_CANARY_CAPABILITIES", "").split(",") if item.strip()
        }))
        return cls(
            mode=mode,
            percentage=percentage,
            capabilities=capabilities,
            has_salt=bool(os.getenv("CHAT_CANARY_SALT", "").strip()),
            high_risk_allowed=str(os.getenv("CHAT_CANARY_ALLOW_HIGH_RISK", "false")).lower() == "true",
        )


def stable_canary_bucket(*, brand: str, sender_id: str, salt: str) -> int:
    if not salt:
        raise ValueError("CHAT_CANARY_SALT is required for stable allocation")
    digest = hmac.new(salt.encode("utf-8"), f"{brand}:{sender_id}".encode("utf-8"), hashlib.sha256).digest()
    return int.from_bytes(digest[:4], "big") % 10_000


def decide_canary(*, brand: str, sender_id: str, capability: str, policy: CanaryPolicy | None = None) -> dict[str, Any]:
    """Return a passive rollout decision; callers must opt in deliberately."""
    policy = policy or CanaryPolicy.from_environment()
    capability = str(capability or "").strip().lower()
    base = {"policy_version": policy.version, "capability": capability, "mode": "control", "bucket": None}
    if policy.mode == "off" or policy.percentage == 0:
        return {**base, "reason": "CANARY_DISABLED"}
    if not policy.has_salt:
        return {**base, "reason": "CANARY_SALT_MISSING"}
    if capability not in policy.capabilities:
        return {**base, "reason": "CAPABILITY_NOT_APPROVED"}
    if policy.mode == "canary" and capability in _HIGH_RISK_CAPABILITIES and not policy.high_risk_allowed:
        return {**base, "reason": "HIGH_RISK_CAPABILITY_BLOCKED"}
    bucket = stable_canary_bucket(brand=brand, sender_id=sender_id, salt=os.environ["CHAT_CANARY_SALT"])
    if bucket >= policy.percentage * 100:
        return {**base, "bucket": bucket, "reason": "OUTSIDE_PERCENTAGE"}
    selected_mode = "shadow" if policy.mode == "shadow" else "canary"
    return {**base, "mode": selected_mode, "bucket": bucket, "reason": "SHADOW_ONLY" if selected_mode == "shadow" else "ELIGIBLE"}


def canary_policy_status(policy: CanaryPolicy | None = None) -> dict[str, Any]:
    policy = policy or CanaryPolicy.from_environment()
    payload = asdict(policy)
    payload["enabled"] = bool(policy.mode in {"shadow", "canary"} and policy.percentage and policy.has_salt)
    return payload
