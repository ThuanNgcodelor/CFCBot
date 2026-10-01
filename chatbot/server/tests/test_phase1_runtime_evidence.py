import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import chat_pipeline  # noqa: E402
import ai_engine  # noqa: E402
from evidence_trace import (  # noqa: E402
    begin_request_trace,
    build_answer_trace,
    end_request_trace,
    latest_provider_trace,
    record_provider_attempt,
)
from runtime_manifest import _redact_config, build_runtime_manifest, get_runtime_manifest  # noqa: E402


class FakeRedis:
    async def get(self, _key):
        return None


class PhaseOneRuntimeEvidenceTests(unittest.IsolatedAsyncioTestCase):
    def test_manifest_is_immutable_and_redacts_secret_shape(self):
        redacted = _redact_config({
            "api_key": "super-secret",
            "nested": {"password": "another-secret", "mode": "safe"},
        })
        manifest_one = get_runtime_manifest()
        manifest_two = get_runtime_manifest()

        self.assertEqual(redacted["api_key"], "<redacted>")
        self.assertEqual(redacted["nested"]["password"], "<redacted>")
        self.assertEqual(manifest_one["runtime_manifest_id"], manifest_two["runtime_manifest_id"])
        self.assertNotIn("super-secret", str(manifest_one))
        self.assertIn("chatbot/server/chat_pipeline.py", manifest_one["files"])

    def test_manifest_id_is_stable_across_process_start_times(self):
        first = build_runtime_manifest(started_at="2026-09-09T00:00:00+00:00")
        second = build_runtime_manifest(started_at="2026-09-09T01:00:00+00:00")
        self.assertNotEqual(first["started_at"], second["started_at"])
        self.assertEqual(first["runtime_manifest_id"], second["runtime_manifest_id"])

    async def test_trace_never_treats_model_as_evidence_or_keeps_phone_plaintext(self):
        token = begin_request_trace()
        try:
            record_provider_attempt(
                provider="groq",
                model="test-model",
                prompt="Số điện thoại 0901234567",
                system_prompt="system",
                prompt_id="test.prompt.v1",
                execution_mode="cloud",
                status="success",
                latency_ms=12.4,
            )
            trace = build_answer_trace(
                answer="Dạ số của bạn là 0901234567",
                intent="cfc_dosage_usage_review",
                source_id="ollama:cfc_agronomy",
                query_plan={"intent": "cfc_dosage_usage_review"},
            )
        finally:
            end_request_trace(token)

        self.assertEqual(trace["evidence"], [])
        self.assertEqual(trace["claims"][0]["status"], "blocked")
        self.assertNotIn("0901234567", trace["claims"][0]["text"])
        self.assertEqual(trace["generator"]["provider"], "groq")
        self.assertEqual(trace["generator"]["model"], "test-model")
        self.assertNotIn("0901234567", str(trace["generator"]))

    async def test_finalized_response_and_history_receive_answer_and_manifest_ids(self):
        sender = "phase1-trace"
        key = f"cfc:session:messenger:{sender}"
        chat_pipeline._local_session_cache.clear()
        chat_pipeline._local_session_cache[key] = {
            "last_user_message": "Website chính thức?",
            "last_bot_reply": "https://cfccobay.com",
            "last_intent": "cfc_company_website",
            "conversation_state": chat_pipeline._default_conversation_state("cfc"),
            "last_trace": {
                "source_id": "cfc_faq_split_v1",
                "query_plan": {"intent": "cfc_company_website"},
            },
        }
        request = chat_pipeline.ChatPipelineRequest(brand="cfc", sender_id=sender, text="Website chính thức?")
        response = chat_pipeline.ChatPipelineResponse(
            answer="https://cfccobay.com",
            intent="cfc_company_website",
            confidence="high",
            score=1.0,
            brand="CFC",
        )
        original_get_redis = chat_pipeline.get_redis
        chat_pipeline.get_redis = lambda: _async_value(FakeRedis())
        try:
            await chat_pipeline._finalize_pipeline_response(request, response)
        finally:
            chat_pipeline.get_redis = original_get_redis

        persisted = chat_pipeline._local_session_cache[key]["last_trace"]
        self.assertTrue(response.answer_id.startswith("ans:"))
        self.assertEqual(response.runtime_manifest_id, persisted["runtime_manifest_id"])
        self.assertEqual(persisted["answer_trace"]["answer_id"], response.answer_id)
        self.assertEqual(persisted["answer_trace"]["claims"][0]["status"], "verified")

    def test_latest_provider_trace_is_redacted_metadata_only(self):
        last = latest_provider_trace()
        self.assertIn("attempts", last)
        self.assertNotIn("api_key", str(last).lower())

    async def test_generate_records_every_skipped_provider_without_prompt_content(self):
        token = begin_request_trace()
        try:
            original_settings = ai_engine._load_settings
            ai_engine._load_settings = lambda: {"ai_providers": {"execution_mode": "cloud"}, "ollama": {}}
            try:
                result = await ai_engine.generate_ai_text(
                    prompt="Số điện thoại 0901234567",
                    prompt_id="test.provider.v1",
                )
            finally:
                ai_engine._load_settings = original_settings
        finally:
            end_request_trace(token)

        self.assertFalse(result["success"])
        attempts = latest_provider_trace()["attempts"]
        self.assertEqual([item["provider"] for item in attempts], ["groq", "gemini", "openrouter"])
        self.assertTrue(all(item["status"] == "skipped" for item in attempts))
        self.assertNotIn("0901234567", str(attempts))


async def _async_value(value):
    return value


if __name__ == "__main__":
    unittest.main()
