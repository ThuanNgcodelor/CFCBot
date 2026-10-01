import os
import sys
import tempfile
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from evaluation_ops import (  # noqa: E402
    CanaryPolicy,
    build_dataset_manifest,
    build_shadow_event,
    decide_canary,
    evaluation_report_envelope,
)


class EvaluationOpsTests(unittest.TestCase):
    def test_dataset_manifest_is_hash_pinned_and_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "one.jsonl"
            second = root / "two.jsonl"
            first.write_text('{"id":"case-one","turns":[]}\n', encoding="utf-8")
            second.write_text('{"id":"case-two","turns":[]}\n', encoding="utf-8")
            manifest = build_dataset_manifest([first, second])
            self.assertEqual(manifest["datasets"][0]["case_count"], 1)
            self.assertTrue(manifest["dataset_manifest_id"].startswith("sha256:"))

            second.write_text('{"id":"case-one","turns":[]}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                build_dataset_manifest([first, second])

    def test_report_envelope_pins_runtime_and_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text('{"id":"case","turns":[]}\n', encoding="utf-8")
            report = evaluation_report_envelope(
                {"generated_at": "2026-08-29T00:00:00Z"},
                dataset_paths=[path],
                validation_mode="unit_static",
            )
        self.assertEqual(report["validation_mode"], "unit_static")
        self.assertIn("runtime_manifest_id", report["runtime_manifest"])
        self.assertTrue(report["report_id"].startswith("eval:"))

    def test_report_rejects_unclassified_validation_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text('{"id":"case","turns":[]}\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                evaluation_report_envelope(
                    {}, dataset_paths=[path], validation_mode="looks_good_locally"
                )

    def test_shadow_event_has_no_raw_query_or_phone(self):
        event = build_shadow_event(
            event_type="nlu", brand="cfc", sender_id="sender-123", message_id="mid-123",
            deterministic_proposal={"intent": "cfc_order_status_request"},
            semantic_proposal={"intent": "order_status_followup", "confidence": 0.9},
            actual_route="cfc_order_status_request",
            trace={"fallback_reason": "", "answer_trace": {"answer_id": "ans:test", "claims": [{"status": "verified"}]}},
            status="predicted", timing_ms=12.3,
        )
        rendered = str(event)
        self.assertNotIn("sender-123", rendered)
        self.assertNotIn("0908776655", rendered)
        self.assertNotIn("query", event)
        self.assertEqual(event["claim_statuses"], ["verified"])

    def test_canary_defaults_to_control_and_high_risk_is_blocked_without_explicit_gate(self):
        disabled = decide_canary(brand="cfc", sender_id="sender", capability="clarification", policy=CanaryPolicy("off", 0, (), False, False))
        self.assertEqual(disabled["mode"], "control")
        self.assertEqual(disabled["reason"], "CANARY_DISABLED")

        prior_salt = os.environ.get("CHAT_CANARY_SALT")
        os.environ["CHAT_CANARY_SALT"] = "test-only-salt"
        try:
            policy = CanaryPolicy("canary", 100, ("order_status",), True, False)
            blocked = decide_canary(brand="cfc", sender_id="sender", capability="order_status", policy=policy)
        finally:
            if prior_salt is None:
                os.environ.pop("CHAT_CANARY_SALT", None)
            else:
                os.environ["CHAT_CANARY_SALT"] = prior_salt
        self.assertEqual(blocked["mode"], "control")
        self.assertEqual(blocked["reason"], "HIGH_RISK_CAPABILITY_BLOCKED")

    def test_shadow_never_becomes_canary_traffic(self):
        prior_salt = os.environ.get("CHAT_CANARY_SALT")
        os.environ["CHAT_CANARY_SALT"] = "test-only-salt"
        try:
            policy = CanaryPolicy("shadow", 100, ("clarification",), True, False)
            decision = decide_canary(brand="zeo", sender_id="sender", capability="clarification", policy=policy)
        finally:
            if prior_salt is None:
                os.environ.pop("CHAT_CANARY_SALT", None)
            else:
                os.environ["CHAT_CANARY_SALT"] = prior_salt
        self.assertEqual(decision["mode"], "shadow")
        self.assertEqual(decision["reason"], "SHADOW_ONLY")


if __name__ == "__main__":
    unittest.main()
