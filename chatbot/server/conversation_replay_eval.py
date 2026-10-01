"""Replay multi-turn gold conversations through the real chatbot pipeline."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable
import uuid

from chat_pipeline import ChatPipelineRequest, _local_customer_cache, _local_session_cache, process_chat_pipeline
from evaluation_ops import VALIDATION_MODES, evaluation_report_envelope
from evaluation_safety import block_external_side_effects
from message_idempotency import _keys as _idempotency_keys
from rag_search import get_redis


DEFAULT_CASES = Path(__file__).with_name("eval_conversation_replays.jsonl")


@dataclass
class TurnResult:
    case_id: str
    turn: int
    user: str
    intent: str
    answer: str
    source_id: str
    source_family: str
    claim_statuses: list[str]
    fallback_reason: str
    query_plan_id: str
    runtime_manifest_id: str
    grounding_status: str
    knowledge_class: str
    expected_behavior: str
    suppress_send: bool
    latency_ms: float
    passed: bool
    failures: list[str]


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        value = json.loads(line)
        if not isinstance(value, dict) or not value.get("id") or not isinstance(value.get("turns"), list):
            raise ValueError(f"Invalid replay case at {path}:{line_number}")
        cases.append(value)
    return cases


def _expected_intents(turn: dict[str, Any]) -> set[str]:
    expected = turn.get("expected_intent", [])
    if isinstance(expected, str):
        return {expected} if expected else set()
    return {str(item) for item in expected if item}


def score_turn(
    turn: dict[str, Any],
    *,
    intent: str,
    answer: str,
    trace: dict[str, Any],
    state: dict[str, Any],
    suppress_send: bool = False,
) -> list[str]:
    failures: list[str] = []
    expected_intents = _expected_intents(turn)
    if expected_intents and intent not in expected_intents:
        failures.append(f"intent={intent!r}, expected={sorted(expected_intents)!r}")

    answer_folded = answer.casefold()
    for text in turn.get("answer_contains", []) or []:
        if str(text).casefold() not in answer_folded:
            failures.append(f"answer_missing={text!r}")
    for text in turn.get("answer_not_contains", []) or []:
        if str(text).casefold() in answer_folded:
            failures.append(f"answer_forbidden={text!r}")

    source_id = str(trace.get("source_id") or "")
    if turn.get("require_source") and not source_id:
        failures.append("source_id_missing")
    answer_trace = trace.get("answer_trace") if isinstance(trace.get("answer_trace"), dict) else {}
    evidence = answer_trace.get("evidence") if isinstance(answer_trace.get("evidence"), list) else []
    source_types = {str(item.get("source_type") or "") for item in evidence if isinstance(item, dict)}
    expected_source_family = turn.get("source_family")
    if expected_source_family and str(expected_source_family) not in source_types:
        failures.append(f"source_family={sorted(source_types)!r}, expected={expected_source_family!r}")
    claim_statuses = {
        str(item.get("status") or "")
        for item in (answer_trace.get("claims") or []) if isinstance(item, dict)
    }
    for status in turn.get("required_claim_statuses", []) or []:
        if str(status) not in claim_statuses:
            failures.append(f"claim_status_missing={status!r}")
    for status in turn.get("forbidden_claim_statuses", []) or []:
        if str(status) in claim_statuses:
            failures.append(f"claim_status_forbidden={status!r}")
    if "suppress_send" in turn and bool(turn["suppress_send"]) != suppress_send:
        failures.append(f"suppress_send={suppress_send!r}, expected={bool(turn['suppress_send'])!r}")

    grounding_status = str((trace.get("grounding") or {}).get("status") or "")
    if turn.get("grounding_status") and grounding_status != turn["grounding_status"]:
        failures.append(f"grounding_status={grounding_status!r}, expected={turn['grounding_status']!r}")
    if turn.get("capability_boundary_required"):
        fallback_reason = str(trace.get("fallback_reason") or "")
        has_boundary = bool(
            trace.get("capability_boundary")
            or grounding_status == "safe_fallback"
            or any(marker in fallback_reason for marker in ("NOT_CONNECTED", "NOT_VERIFIED", "REQUIRES_EXPERT_REVIEW"))
        )
        if not has_boundary:
            failures.append("capability_boundary_missing")

    state_expect = turn.get("state", {}) or {}
    if "pending_action" in state_expect:
        actual = (state.get("pending_action") or {}).get("name", "")
        if actual != state_expect["pending_action"]:
            failures.append(f"pending_action={actual!r}, expected={state_expect['pending_action']!r}")
    if "corrections_min" in state_expect:
        actual_count = len(state.get("corrections") or [])
        if actual_count < int(state_expect["corrections_min"]):
            failures.append(f"corrections={actual_count}, expected_min={state_expect['corrections_min']}")
    if "pending_slots" in state_expect:
        actual_slots = set(state.get("pending_slots") or [])
        expected_slots = set(state_expect["pending_slots"] or [])
        if not expected_slots.issubset(actual_slots):
            failures.append(f"pending_slots={sorted(actual_slots)!r}, expected={sorted(expected_slots)!r}")
    if "pending_slots_exact" in state_expect:
        actual_slots = set(state.get("pending_slots") or [])
        expected_slots = set(state_expect["pending_slots_exact"] or [])
        if actual_slots != expected_slots:
            failures.append(f"pending_slots={sorted(actual_slots)!r}, expected_exact={sorted(expected_slots)!r}")
    if "active_goal" in state_expect:
        active_goal = state.get("active_goal") or {}
        actual_goal = active_goal if isinstance(active_goal, str) else str(active_goal.get("name") or "")
        if actual_goal != state_expect["active_goal"]:
            failures.append(f"active_goal={actual_goal!r}, expected={state_expect['active_goal']!r}")
    expected_confirmed = state_expect.get("confirmed_slots") or {}
    actual_confirmed = state.get("confirmed_slots") or {}
    for slot, expected_value in expected_confirmed.items():
        actual_value = actual_confirmed.get(slot)
        if isinstance(expected_value, dict) and isinstance(actual_value, dict):
            mismatch = any(actual_value.get(key) != value for key, value in expected_value.items())
        else:
            mismatch = actual_value != expected_value
        if mismatch:
            failures.append(f"confirmed_slot[{slot}]={actual_value!r}, expected={expected_value!r}")
    for slot in state_expect.get("slot_absent", []) or []:
        if actual_confirmed.get(slot) not in (None, ""):
            failures.append(f"confirmed_slot[{slot}]_should_be_absent={actual_confirmed.get(slot)!r}")
    if "takeover_status" in state_expect:
        actual_status = (state.get("takeover_state") or {}).get("status", "")
        if actual_status != state_expect["takeover_status"]:
            failures.append(f"takeover_status={actual_status!r}, expected={state_expect['takeover_status']!r}")
    return failures


async def _reset_sender(redis_client: Any, brand: str, sender_id: str, *, run_id: str) -> None:
    expected_prefix = f"eval-replay:{run_id}:"
    if not sender_id.startswith(expected_prefix):
        raise ValueError(
            f"Refusing to delete non-evaluation sender state: {sender_id!r} "
            f"does not start with {expected_prefix!r}"
        )
    session_key = f"{brand}:session:messenger:{sender_id}"
    history_key = f"{brand}:history:messenger:{sender_id}"
    customer_key = f"{brand}:customer:messenger:{sender_id}"
    _local_session_cache.pop(session_key, None)
    _local_customer_cache.pop(customer_key, None)
    await redis_client.delete(session_key, history_key, customer_key)


async def _reset_evaluation_message(
    redis_client: Any, brand: str, message_id: str, *, run_id: str,
) -> None:
    expected_prefix = f"eval:{run_id}:"
    if not message_id.startswith(expected_prefix):
        raise ValueError(
            f"Refusing to delete non-evaluation message state: {message_id!r} "
            f"does not start with {expected_prefix!r}"
        )
    lease_key, response_key = _idempotency_keys(brand, message_id)
    await redis_client.delete(lease_key, response_key)


async def run_replays(
    cases: Iterable[dict[str, Any]],
    *,
    dataset_path: Path = DEFAULT_CASES,
    redis_client: Any | None = None,
    process_turn: Callable[[ChatPipelineRequest], Awaitable[Any]] = process_chat_pipeline,
    run_id: str | None = None,
    validation_mode: str = "redis_integration",
) -> dict[str, Any]:
    """Run isolated replays while blocking operator-facing external effects.

    Session/customer/history writes remain enabled only for a unique
    ``eval-replay:<run_id>:`` sender namespace so the real persistence path is
    exercised without touching customer sessions.
    """
    if validation_mode not in VALIDATION_MODES:
        raise ValueError(f"Unsupported validation_mode: {validation_mode!r}")
    case_list = list(cases)
    run_nonce = run_id or uuid.uuid4().hex[:12]
    if not run_nonce or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in run_nonce):
        raise ValueError("run_id must contain only letters, numbers, '-' or '_'")
    if redis_client is None:
        redis_client = await get_redis()
    redis_available = False
    ping = getattr(redis_client, "ping", None)
    if callable(ping):
        try:
            redis_available = bool(await ping())
        except Exception:
            redis_available = False
    results: list[TurnResult] = []
    case_passes = 0
    source_required = 0
    source_present = 0
    knowledge_totals: dict[str, int] = {}
    knowledge_passes: dict[str, int] = {}
    memory_required = memory_passed = 0
    routing_required = routing_passed = 0
    grounding_required = grounding_passed = 0
    task_required = task_passed = 0

    with block_external_side_effects():
        for case in case_list:
            case_id = str(case["id"])
            brand = str(case.get("brand") or "zeo").lower()
            if brand not in {"cfc", "zeo"}:
                raise ValueError(f"Unsupported replay brand in {case_id!r}: {brand!r}")
            sender_id = f"eval-replay:{run_nonce}:{case_id}"
            await _reset_sender(redis_client, brand, sender_id, run_id=run_nonce)
            case_ok = True
            evaluation_message_ids: list[str] = []
            try:
                for index, turn in enumerate(case["turns"], start=1):
                    message_id = f"eval:{run_nonce}:{case_id}:{index}"
                    evaluation_message_ids.append(message_id)
                    response = await process_turn(ChatPipelineRequest(
                        brand=brand,
                        sender_id=sender_id,
                        text=str(turn.get("user") or ""),
                        fb_name="Conversation Replay Eval",
                        message_id=message_id,
                        input_kind=str(turn.get("input_kind") or "text"),
                        latitude=turn.get("latitude"),
                        longitude=turn.get("longitude"),
                        attachment_type=str(turn.get("attachment_type") or ""),
                    ))
                    session = _local_session_cache.get(f"{brand}:session:messenger:{sender_id}") or {}
                    trace = session.get("last_trace") or {}
                    state = session.get("conversation_state") or {}
                    failures = score_turn(
                        turn,
                        intent=response.intent,
                        answer=response.answer,
                        trace=trace,
                        state=state,
                        suppress_send=response.suppress_send,
                    )
                    if turn.get("require_source"):
                        source_required += 1
                        source_present += int(bool(trace.get("source_id")))
                    routing_applicable = bool(_expected_intents(turn))
                    memory_applicable = bool(turn.get("state"))
                    grounding_applicable = bool(
                        turn.get("require_source")
                        or turn.get("capability_boundary_required")
                        or turn.get("grounding_status")
                        or turn.get("answer_not_contains")
                    )
                    task_applicable = bool(
                        turn.get("task_completion_applicable", case.get("task_completion_applicable", False))
                    )
                    routing_failures = [item for item in failures if item.startswith("intent=")]
                    memory_prefixes = (
                        "pending_action=", "corrections=", "pending_slots=", "active_goal=",
                        "confirmed_slot[", "takeover_status=",
                    )
                    memory_failures = [item for item in failures if item.startswith(memory_prefixes)]
                    grounding_prefixes = (
                        "source_id_missing", "grounding_status=", "capability_boundary_missing",
                        "answer_forbidden=",
                    )
                    grounding_failures = [item for item in failures if item.startswith(grounding_prefixes)]
                    if routing_applicable:
                        routing_required += 1
                        routing_passed += int(not routing_failures)
                    if memory_applicable:
                        memory_required += 1
                        memory_passed += int(not memory_failures)
                    if grounding_applicable:
                        grounding_required += 1
                        grounding_passed += int(not grounding_failures)
                    if task_applicable:
                        task_required += 1
                        task_passed += int(not failures)
                    case_ok = case_ok and not failures
                    knowledge_class = str(turn.get("knowledge_class") or case.get("knowledge_class") or "unclassified")
                    expected_behavior = str(turn.get("expected_behavior") or case.get("expected_behavior") or "")
                    knowledge_totals[knowledge_class] = knowledge_totals.get(knowledge_class, 0) + 1
                    knowledge_passes[knowledge_class] = knowledge_passes.get(knowledge_class, 0) + int(not failures)
                    results.append(TurnResult(
                        case_id=case_id,
                        turn=index,
                        user=str(turn.get("user") or ""),
                        intent=response.intent,
                        answer=response.answer,
                        source_id=str(trace.get("source_id") or ""),
                        source_family="+".join(sorted({
                            str(item.get("source_type") or "")
                            for item in ((trace.get("answer_trace") or {}).get("evidence") or [])
                            if isinstance(item, dict) and item.get("source_type")
                        })),
                        claim_statuses=sorted({
                            str(item.get("status") or "")
                            for item in ((trace.get("answer_trace") or {}).get("claims") or [])
                            if isinstance(item, dict) and item.get("status")
                        }),
                        fallback_reason=str(trace.get("fallback_reason") or response.fallback_reason or ""),
                        query_plan_id=str((trace.get("answer_trace") or {}).get("query_plan_id") or ""),
                        runtime_manifest_id=str(trace.get("runtime_manifest_id") or ""),
                        grounding_status=str((trace.get("grounding") or {}).get("status") or ""),
                        knowledge_class=knowledge_class,
                        expected_behavior=expected_behavior,
                        suppress_send=response.suppress_send,
                        latency_ms=float(response.latency_ms or 0.0),
                        passed=not failures,
                        failures=failures,
                    ))
                case_passes += int(case_ok)
            finally:
                await _reset_sender(redis_client, brand, sender_id, run_id=run_nonce)
                for message_id in evaluation_message_ids:
                    await _reset_evaluation_message(
                        redis_client, brand, message_id, run_id=run_nonce,
                    )

    result_dicts = [asdict(item) for item in results]
    total_turns = len(result_dicts)
    passed_turns = sum(1 for item in result_dicts if item["passed"])
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "validation_mode": validation_mode,
        "run_id": run_nonce,
        "sender_namespace": f"eval-replay:{run_nonce}:",
        "side_effect_policy": {
            "external_notifications": "blocked",
            "amis_writes": "not_invoked",
            "redis_writes": "evaluation_sender_and_message_namespaces_only",
            "redis_cleanup": "confirmed",
        },
        "dependencies": {
            "redis": "available" if redis_available else "unavailable",
        },
        "summary": {
            "cases": len(case_list),
            "cases_passed": case_passes,
            "turns": total_turns,
            "turns_passed": passed_turns,
            "turn_pass_rate": round(passed_turns / total_turns, 4) if total_turns else 0.0,
            "source_coverage": round(source_present / source_required, 4) if source_required else 1.0,
            "knowledge_class_pass_rate": {
                key: round(knowledge_passes.get(key, 0) / total, 4) if total else 0.0
                for key, total in sorted(knowledge_totals.items())
            },
            "quality_scores": {
                "memory_score_10": round(memory_passed / memory_required * 10, 2) if memory_required else None,
                "routing_score_10": round(routing_passed / routing_required * 10, 2) if routing_required else None,
                "grounding_score_10": round(grounding_passed / grounding_required * 10, 2) if grounding_required else None,
                "task_completion": (
                    round(task_passed / task_required, 4) if task_required else "not_applicable"
                ),
                "sample_sizes": {
                    "memory_turns": memory_required,
                    "routing_turns": routing_required,
                    "grounding_turns": grounding_required,
                    "task_turns": task_required,
                },
            },
        },
        "results": result_dicts,
    }
    return evaluation_report_envelope(
        report, dataset_paths=[dataset_path], validation_mode=report["validation_mode"],
    )


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--validation-mode",
        choices=sorted(VALIDATION_MODES),
        default="redis_integration",
    )
    args = parser.parse_args()
    redis_client = await get_redis()
    try:
        report = await run_replays(
            load_cases(args.cases),
            dataset_path=args.cases,
            redis_client=redis_client,
            validation_mode=args.validation_mode,
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
    finally:
        close = getattr(redis_client, "aclose", None)
        if callable(close):
            await close()
    return 0 if report["summary"]["turn_pass_rate"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
