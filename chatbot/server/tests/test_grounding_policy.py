import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from grounding_policy import assess_grounding  # noqa: E402


class GroundingPolicyTests(unittest.TestCase):
    def test_contact_and_price_require_source(self):
        for intent in ("company_contact_information", "specific_product_pricing"):
            with self.subTest(intent=intent):
                decision = assess_grounding(intent=intent)
                self.assertEqual(decision.status, "missing_source")
                self.assertTrue(decision.requires_source)

    def test_source_satisfies_high_risk_claim(self):
        decision = assess_grounding(
            intent="shopee_product_link",
            source_id="zeo:shopee_catalog:123",
        )
        self.assertEqual(decision.status, "grounded")
        self.assertEqual(decision.claim_type, "purchase_link")

    def test_explicit_unverified_response_is_safe_fallback(self):
        decision = assess_grounding(intent="return_fee_unverified")
        self.assertEqual(decision.status, "safe_fallback")

    def test_greeting_does_not_need_source(self):
        decision = assess_grounding(intent="greeting")
        self.assertEqual(decision.status, "safe_fallback")
        self.assertFalse(decision.requires_source)

    def test_model_provider_is_never_business_evidence(self):
        for source_id in (
            "ollama:cfc_agronomy",
            "groq:llama",
            "openrouter:deepseek",
            "gemini:flash",
            "openai:gpt",
        ):
            with self.subTest(source_id=source_id):
                decision = assess_grounding(
                    intent="cfc_dosage_usage_review",
                    source_id=source_id,
                )
                self.assertEqual(decision.status, "blocked_unsupported_claim")
                self.assertEqual(decision.source_id, "")
                self.assertEqual(decision.reason, "GENERATOR_IS_NOT_EVIDENCE")

    def test_agronomy_claim_requires_source(self):
        decision = assess_grounding(intent="cfc_crop_consultation_request")
        self.assertEqual(decision.status, "missing_source")
        self.assertEqual(decision.claim_type, "technical_or_safety")


if __name__ == "__main__":
    unittest.main()
