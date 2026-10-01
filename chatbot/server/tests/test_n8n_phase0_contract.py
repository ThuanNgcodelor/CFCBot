import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / "workflows" / "local-n8n"


class ChatbotWorkflowContainmentTests(unittest.TestCase):
    def _read(self, filename: str) -> str:
        return (WORKFLOWS / filename).read_text(encoding="utf-8")

    def test_chatbot_http_errors_never_route_to_messenger_reply(self):
        for filename in ("zeo_chatbot.workflow.ts", "cfc_cobay_chatbot.workflow.ts"):
            with self.subTest(filename=filename):
                workflow = self._read(filename)
                self.assertNotIn("onError: 'continueErrorOutput'", workflow)
                self.assertNotRegex(
                    workflow,
                    r"GoiFastApiChatPipeline\.error\(\)\.to\(this\.PrepareMessengerReply",
                )

    def test_malformed_empty_duplicate_and_takeover_responses_are_suppressed(self):
        for filename in ("zeo_chatbot.workflow.ts", "cfc_cobay_chatbot.workflow.ts"):
            with self.subTest(filename=filename):
                workflow = self._read(filename)
                for contract in (
                    "pipelineRes.error",
                    "pipelineRes.duplicate === true",
                    "pipelineRes.suppress_send === true",
                    "'duplicate_in_flight'",
                    "'human_handoff_active'",
                    "if (!finalReply)",
                    "return [];",
                ):
                    self.assertIn(contract, workflow)

    def test_cfc_location_contract_reaches_fastapi(self):
        workflow = self._read("cfc_cobay_chatbot.workflow.ts")
        for contract in (
            "payload?.coordinates",
            "input_kind: $json.inputKind",
            "attachment_type: $json.attachmentType",
            "latitude: $json.latitude",
            "longitude: $json.longitude",
        ):
            self.assertIn(contract, workflow)


class KnowledgeWorkflowCheckpointTests(unittest.TestCase):
    def _assert_checkpoint_order(self, filename: str, prefix: str) -> None:
        workflow = (WORKFLOWS / filename).read_text(encoding="utf-8")
        candidate_key = f"{prefix}:kb:basic:candidate"
        active_key = f"{prefix}:kb:basic:active"
        for contract in (
            candidate_key,
            active_key,
            "snapshot_validated",
            "vector_rebuilt",
            "hot_cache_refreshed",
            "KNOWLEDGE_SYNC_INCOMPLETE",
            "complete",
        ):
            self.assertIn(contract, workflow)

        if prefix == "cfc":
            links = (
                "WriteCfcRedisCandidate.out(0).to(this.RebuildCfcVectorIndex",
                "RebuildCfcVectorIndex.out(0).to(this.ValidateCfcSync",
                "ValidateCfcSync.out(0).to(this.PromoteCfcRedisSnapshot",
                "PromoteCfcRedisSnapshot.out(0).to(this.WriteCfcRedisSyncMetadata",
            )
            rebuild_name = "Rebuild CFC Vector Index"
            rebuild_property = "RebuildCfcVectorIndex = {"
        else:
            links = (
                "WriteRedisCandidate.out(0).to(this.RebuildZeoVectorIndex",
                "RebuildZeoVectorIndex.out(0).to(this.ValidateZeoSync",
                "ValidateZeoSync.out(0).to(this.PromoteRedisSnapshot",
                "PromoteRedisSnapshot.out(0).to(this.WriteRedisSyncMetadata",
            )
            rebuild_name = "Rebuild ZeO Vector Index"
            rebuild_property = "RebuildZeoVectorIndex = {"

        offsets = [workflow.index(link) for link in links]
        self.assertEqual(offsets, sorted(offsets))
        rebuild_start = workflow.index(f"name: '{rebuild_name}'")
        rebuild_end = workflow.index(rebuild_property, rebuild_start)
        self.assertNotIn("continueRegularOutput", workflow[rebuild_start:rebuild_end])

    def test_cfc_candidate_is_promoted_only_after_complete_rebuild(self):
        self._assert_checkpoint_order("cfc_knowledge_sync_basic.workflow.ts", "cfc")

    def test_zeo_candidate_is_promoted_only_after_complete_rebuild(self):
        self._assert_checkpoint_order("zeo_knowledge_sync_basic.workflow.ts", "zeo")


if __name__ == "__main__":
    unittest.main()
