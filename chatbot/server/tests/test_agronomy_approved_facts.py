import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.agronomy.facts import (  # noqa: E402
    approved_fact_status,
    resolve_approved_agronomy_fact,
    validate_agronomy_fact,
)


class ApprovedAgronomyFactTests(unittest.TestCase):
    def test_active_customer_eligibility_fact_is_resolvable(self):
        fact = resolve_approved_agronomy_fact(crop="sầu riêng")

        self.assertIsNotNone(fact)
        self.assertEqual(fact["fact_id"], "cfc-product-family-eligibility-durian-v1")
        self.assertEqual(fact["source_id"], "cfc_reply_docx_v1")
        self.assertNotRegex(fact["answer"], r"\b\d+\s*(kg|ha)\b")

    def test_draft_or_expired_technical_fact_is_never_customer_safe(self):
        draft = {
            "fact_id": "draft-dose",
            "brand": "cfc",
            "fact_type": "protocol",
            "crops": ["sầu riêng"],
            "stages": ["nuôi trái"],
            "answer": "Bón 100 kg/ha.",
            "source_id": "source-v1",
            "source_locator": "sheet#row=1",
            "approval_status": "draft",
            "approved_at": "2026-08-29",
            "approved_by": "Kỹ sư A",
        }
        expired = dict(draft, approval_status="approved", valid_until="2000-01-01T00:00:00+00:00")

        self.assertEqual(validate_agronomy_fact(draft)[1], "FACT_NOT_APPROVED")
        self.assertEqual(validate_agronomy_fact(expired)[1], "FACT_EXPIRED")

    def test_technical_fact_requires_named_approver_and_eligibility_cannot_smuggle_dose(self):
        technical = {
            "fact_id": "protocol-without-approver",
            "brand": "cfc",
            "fact_type": "protocol",
            "crops": ["sầu riêng"],
            "stages": ["nuôi trái"],
            "answer": "Hướng dẫn đã duyệt.",
            "source_id": "source-v1",
            "source_locator": "sheet#row=1",
            "approval_status": "approved",
            "approved_at": "2026-08-29",
        }
        eligibility = dict(technical, fact_id="eligibility-dose", fact_type="eligibility", answer="Dùng 5 kg/gốc.")

        self.assertEqual(validate_agronomy_fact(technical)[1], "FACT_TECHNICAL_APPROVER_MISSING")
        self.assertEqual(validate_agronomy_fact(eligibility)[1], "FACT_DOSAGE_NOT_ALLOWED")

    def test_status_is_aggregate_only(self):
        status = approved_fact_status(now=datetime(2026, 8, 29, tzinfo=timezone.utc))

        self.assertEqual(status["approved_count"], 1)
        self.assertEqual(status["by_type"]["eligibility"], 1)
        self.assertNotIn("answer", str(status).lower())


if __name__ == "__main__":
    unittest.main()
