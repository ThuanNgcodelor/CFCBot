import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
from evaluation_ops import VALIDATION_MODES, build_dataset_manifest  # noqa: E402
from phase0_contract import (  # noqa: E402
    CAPABILITY_CONTRACTS,
    CHAT_PIPELINE_REQUEST_FIELDS,
    CHAT_PIPELINE_RESPONSE_FIELDS,
    CONVERSATION_STATE_V5_FIELDS,
    FROZEN_DATASETS,
    REDIS_KEY_CONTRACT,
)
from runtime_manifest import get_runtime_manifest  # noqa: E402


class PhaseZeroBaselineContractTests(unittest.TestCase):
    def test_public_request_and_response_fields_are_frozen(self):
        self.assertEqual(
            tuple(chat_pipeline.ChatPipelineRequest.model_fields),
            CHAT_PIPELINE_REQUEST_FIELDS,
        )
        self.assertEqual(
            tuple(chat_pipeline.ChatPipelineResponse.model_fields),
            CHAT_PIPELINE_RESPONSE_FIELDS,
        )

    def test_schema_v5_state_keeps_every_frozen_field(self):
        state = chat_pipeline._load_conversation_state({}, "cfc")
        expected_before_persist = set(CONVERSATION_STATE_V5_FIELDS) - {"state_revision"}
        self.assertEqual(set(state), expected_before_persist)
        self.assertEqual(state["schema_version"], 5)

    def test_capability_and_redis_inventory_is_complete(self):
        self.assertEqual(set(CAPABILITY_CONTRACTS), {
            "product", "dealer", "order", "loyalty", "price_intake", "purchase_intake",
            "agronomy", "contact", "complaint", "b2b", "handoff", "fallback",
        })
        self.assertEqual(
            {name for name, value in CAPABILITY_CONTRACTS.items() if value["risk"] == "protected_read"},
            {"order", "loyalty"},
        )
        for key in ("conversation_session", "conversation_history", "customer_profile", "sender_lease"):
            self.assertIn(key, REDIS_KEY_CONTRACT)

    def test_evaluation_datasets_are_frozen_at_19_and_40_unique_cases(self):
        manifest = build_dataset_manifest([
            SERVER_DIR / "eval_conversation_replays.jsonl",
            SERVER_DIR / "eval_sheet_grounding_cases.jsonl",
        ])
        self.assertEqual(
            [item["case_count"] for item in manifest["datasets"]],
            [19, 40],
        )
        actual = {
            item["path"]: {"case_count": item["case_count"], "sha256": item["sha256"]}
            for item in manifest["datasets"]
        }
        self.assertEqual(actual, FROZEN_DATASETS)

    def test_validation_modes_are_explicit(self):
        self.assertEqual(VALIDATION_MODES, {
            "unit_static", "pipeline_fixture", "ollama_local", "redis_integration", "live_canary",
        })

    def test_runtime_manifest_covers_routing_state_adapters_and_contracts(self):
        manifest = get_runtime_manifest()
        for path in (
            "chatbot/server/chat_pipeline.py",
            "chatbot/server/dialogue_router.py",
            "chatbot/server/conversation_orchestrator.py",
            "chatbot/server/conversation_store.py",
            "chatbot/server/domains/amis/client.py",
            "chatbot/server/domains/amis/order_cache.py",
            "chatbot/server/domains/amis/loyalty_cache.py",
            "chatbot/server/main.py",
            "compose.yaml",
            "scripts/cfcbot",
            "workflows/local-n8n/cfc_cobay_chatbot.workflow.ts",
        ):
            self.assertIn(path, manifest["files"])
            self.assertNotEqual(manifest["files"][path], "missing")
        fingerprints = manifest["compatibility"]["fingerprints"]
        self.assertEqual(set(fingerprints), {
            "chat_pipeline_request.v1", "chat_pipeline_response.v1", "conversation_state.v5",
            "redis_keys.v1", "capabilities.v1", "datasets.v1",
        })


if __name__ == "__main__":
    unittest.main()
