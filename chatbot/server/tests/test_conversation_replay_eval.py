import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
import telegram_notifier  # noqa: E402
from conversation_orchestrator import schedule_conversation_shadow  # noqa: E402
from conversation_replay_eval import (  # noqa: E402
    DEFAULT_CASES,
    _reset_evaluation_message,
    _reset_sender,
    load_cases,
    run_replays,
    score_turn,
)
from evaluation_safety import block_external_side_effects  # noqa: E402
from message_idempotency import _keys as idempotency_keys  # noqa: E402
from nlu_shadow import schedule_nlu_shadow  # noqa: E402


class FakeRedis:
    def __init__(self):
        self.deleted = []

    async def ping(self):
        return True

    async def delete(self, *keys):
        self.deleted.extend(keys)


class ConversationReplayEvalTests(unittest.TestCase):
    def test_gold_file_loads_multi_turn_cases(self):
        cases = load_cases(DEFAULT_CASES)
        self.assertGreaterEqual(len(cases), 16)
        self.assertTrue(any(len(case["turns"]) > 1 for case in cases))

    def test_invalid_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text('{"id":"missing-turns"}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_cases(path)

    def test_scorer_checks_intent_source_and_context_state(self):
        failures = score_turn(
            {
                "expected_intent": "company_contact_information",
                "answer_contains": ["1900 5307"],
                "require_source": True,
                "state": {"pending_action": "send_product_link", "corrections_min": 1},
            },
            intent="fallback_low_confidence",
            answer="Chưa có dữ liệu",
            trace={},
            state={"pending_action": {}, "corrections": []},
        )
        self.assertTrue(any(item.startswith("intent=") for item in failures))
        self.assertIn("source_id_missing", failures)
        self.assertTrue(any(item.startswith("pending_action=") for item in failures))
        self.assertTrue(any(item.startswith("corrections=") for item in failures))

    def test_scorer_checks_cfc_goal_confirmed_slots_and_capability_boundary(self):
        failures = score_turn(
            {
                "expected_intent": "cfc_inventory_unavailable",
                "capability_boundary_required": True,
                "state": {
                    "active_goal": "inventory_check",
                    "confirmed_slots": {"formula": "16-16-8 TE", "phone": "0979176415"},
                    "pending_slots_exact": ["area"],
                },
            },
            intent="cfc_inventory_unavailable",
            answer="Hệ thống chưa kết nối tồn kho realtime.",
            trace={
                "fallback_reason": "INVENTORY_TOOL_NOT_CONNECTED",
                "grounding": {"status": "safe_fallback"},
            },
            state={
                "active_goal": {"name": "inventory_check"},
                "confirmed_slots": {"formula": "16-16-8 TE", "phone": "0979176415"},
                "pending_slots": ["area"],
            },
        )
        self.assertEqual(failures, [])


class ConversationReplayIsolationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_customer_cache.clear()

    async def test_custom_dataset_manifest_namespace_and_external_effect_guard(self):
        redis = FakeRedis()
        seen_requests = []
        notification_results = []

        async def process_turn(request):
            seen_requests.append(request)
            notification_results.append(await telegram_notifier.send_telegram_message(
                "must stay local", bot_token="configured", chat_id="configured"
            ))
            session_key = f"{request.brand}:session:messenger:{request.sender_id}"
            chat_pipeline._local_session_cache[session_key] = {
                "last_trace": {},
                "conversation_state": chat_pipeline._load_conversation_state({}, request.brand),
            }
            return chat_pipeline.ChatPipelineResponse(
                answer="Xin chào", intent="greeting", confidence="high", score=1.0,
                brand=request.brand.upper(), latency_ms=2.5,
            )

        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "custom-cases.jsonl"
            dataset.write_text(
                '{"id":"same-text","brand":"zeo","turns":['
                '{"user":"Alo","expected_intent":"greeting"},'
                '{"user":"Alo","expected_intent":"greeting"}]}\n',
                encoding="utf-8",
            )
            with patch("telegram_notifier.httpx.AsyncClient") as http_client:
                report = await run_replays(
                    load_cases(dataset),
                    dataset_path=dataset,
                    redis_client=redis,
                    process_turn=process_turn,
                    run_id="phase0test",
                    validation_mode="pipeline_fixture",
                )

        self.assertEqual(report["dataset_manifest"]["datasets"][0]["path"], "custom-cases.jsonl")
        self.assertEqual(report["validation_mode"], "pipeline_fixture")
        self.assertEqual(report["sender_namespace"], "eval-replay:phase0test:")
        self.assertEqual(report["side_effect_policy"]["external_notifications"], "blocked")
        self.assertEqual(report["side_effect_policy"]["redis_cleanup"], "confirmed")
        self.assertEqual([request.message_id for request in seen_requests], [
            "eval:phase0test:same-text:1", "eval:phase0test:same-text:2",
        ])
        self.assertTrue(all(request.sender_id == "eval-replay:phase0test:same-text" for request in seen_requests))
        self.assertTrue(all(item["reason"] == "EVALUATION_EXTERNAL_SIDE_EFFECT_BLOCKED" for item in notification_results))
        self.assertFalse(http_client.called)
        expected_message_keys = set()
        for message_id in ("eval:phase0test:same-text:1", "eval:phase0test:same-text:2"):
            expected_message_keys.update(idempotency_keys("zeo", message_id))
        self.assertTrue(expected_message_keys.issubset(set(redis.deleted)))
        non_message_keys = set(redis.deleted) - expected_message_keys
        self.assertTrue(non_message_keys)
        self.assertTrue(all(":eval-replay:phase0test:" in key for key in non_message_keys))

    async def test_reset_refuses_customer_sender_namespace(self):
        redis = FakeRedis()
        with self.assertRaises(ValueError):
            await _reset_sender(redis, "cfc", "real-customer-123", run_id="phase0test")
        with self.assertRaises(ValueError):
            await _reset_evaluation_message(
                redis, "cfc", "real-message-123", run_id="phase0test"
            )
        self.assertEqual(redis.deleted, [])

    async def test_evaluation_guard_blocks_shadow_and_background_profile_writes(self):
        with block_external_side_effects(), patch("chat_pipeline.get_redis") as get_redis:
            nlu_status = schedule_nlu_shadow(
                brand="cfc", sender_id="eval", message_id="mid", raw_text="Alo",
                normalized_text="alo", conversation_summary="", deterministic_plan={},
                confidence_threshold=0.8,
            )
            conversation_status = schedule_conversation_shadow(
                brand="cfc", sender_id="eval", message_id="mid", user_query="Alo",
                conversation_messages=[], conversation_context={}, deterministic_plan={},
            )
            await chat_pipeline._async_save_profile_and_notify(
                "cfc", "eval", {}, "0901000000", "", "", ""
            )
            await chat_pipeline._async_update_customer_profile(
                brand="cfc", sender_id="eval", profile={}
            )

        self.assertEqual(nlu_status, "blocked_evaluation")
        self.assertEqual(conversation_status, "blocked_evaluation")
        get_redis.assert_not_called()

    async def test_pipeline_error_still_cleans_sender_and_message_keys(self):
        redis = FakeRedis()

        async def fail(_request):
            raise RuntimeError("fixture failure")

        case = {"id": "failure-cleanup", "brand": "cfc", "turns": [{"user": "Alo"}]}
        with self.assertRaises(RuntimeError):
            await run_replays(
                [case], redis_client=redis, process_turn=fail,
                run_id="cleanupcase", validation_mode="pipeline_fixture",
            )

        lease_key, response_key = idempotency_keys(
            "cfc", "eval:cleanupcase:failure-cleanup:1"
        )
        self.assertIn(lease_key, redis.deleted)
        self.assertIn(response_key, redis.deleted)
        self.assertIn(
            "cfc:session:messenger:eval-replay:cleanupcase:failure-cleanup",
            redis.deleted,
        )


if __name__ == "__main__":
    unittest.main()
