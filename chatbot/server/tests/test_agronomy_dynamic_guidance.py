import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.agronomy.guidance import build_grounded_agronomy_guidance  # noqa: E402
import rag_search  # noqa: E402


CONTACTS = (
    ("Khuyến nông Lê Thanh Đạm", "0353 857 516"),
    ("Khuyến nông Cao Văn Được", "0939 852 529"),
)
KNOWN_CROPS = ("sau rieng", "oi", "nhan", "xoai", "mit", "buoi", "lua")


def _result(*rows, confidence="high"):
    return {
        "confidence": confidence,
        "score": rows[0]["score"] if rows else 0.0,
        "results": list(rows),
    }


def _row(answer, *, intent="fruit_stage", score=0.9, risk="medium", source="test:handbook"):
    return {
        "intent": intent,
        "answer": answer,
        "category": "agronomy",
        "audience": "customer",
        "risk_level": risk,
        "source_id": source,
        "score": score,
    }


class DynamicAgronomyGuidanceTests(unittest.TestCase):
    def test_lexical_category_filter_cannot_return_sales_row_for_agronomy_route(self):
        original_items = rag_search._knowledge_items.get("cfc")
        original_phrases = rag_search._phrase_map.get("cfc")
        original_intents = rag_search._intent_map.get("cfc")
        try:
            rag_search._knowledge_items["cfc"] = [
                {
                    "intent": "sales_price",
                    "answer": "Bảng giá NPK",
                    "category": "sales",
                    "question_examples": "NPK bao nhiêu tiền",
                    "audience": "customer",
                },
                {
                    "intent": "agronomy_stage",
                    "answer": "Hướng dẫn cho giai đoạn trái non",
                    "category": "agronomy",
                    "question_examples": "Trái non nên bón gì",
                    "audience": "customer",
                },
            ]
            rag_search._phrase_map["cfc"] = {}
            rag_search._intent_map["cfc"] = {}
            rows = rag_search.fast_lexical_search(
                "NPK cho trái non nên bón gì",
                "cfc",
                category_filter="agronomy",
            )
            self.assertTrue(rows)
            self.assertTrue(all(row["category"] == "agronomy" for row in rows))
        finally:
            rag_search._knowledge_items["cfc"] = original_items or []
            rag_search._phrase_map["cfc"] = original_phrases or {}
            rag_search._intent_map["cfc"] = original_intents or {}

    def test_same_grounded_stage_rule_supports_guava_and_longan_without_crop_branches(self):
        evidence = _result(_row(
            "Dạ khi cây đang ra hoa, nên cân đối Lân và Kali, bổ sung Canxi, Bo; hạn chế Đạm cao. "
            "Bạn gửi SĐT để kỹ sư tư vấn thêm nhé!"
        ))
        for crop in ("ổi", "nhãn"):
            with self.subTest(crop=crop):
                result = build_grounded_agronomy_guidance(
                    query=f"Cây {crop} ra hoa hay rụng bông nên bón gì?",
                    slots={"crop": crop, "crop_stage": "ra hoa"},
                    search_result=evidence,
                    known_crop_terms=KNOWN_CROPS,
                    contacts=CONTACTS,
                )
                self.assertIn(crop, result["answer"])
                self.assertIn("Canxi, Bo", result["answer"])
                self.assertNotIn("gửi SĐT", result["answer"])
                self.assertFalse(result["requires_expert"])

    def test_crop_specific_source_is_not_reused_for_another_crop(self):
        evidence = _result(_row(
            "Dạ khi sầu riêng đang nhú mũi giáo, ưu tiên NPK cân đối và tránh Đạm cao.",
            intent="durian_shoot",
        ))
        result = build_grounded_agronomy_guidance(
            query="Cây ổi đang nhú đọt nên bón gì?",
            slots={"crop": "ổi", "crop_stage": "nhú đọt"},
            search_result=evidence,
            known_crop_terms=KNOWN_CROPS,
            contacts=CONTACTS,
        )
        self.assertEqual(result["evidence_count"], 0)
        self.assertNotIn("sầu riêng", result["answer"])
        self.assertIn("Lê Thanh Đạm", result["answer"])

    def test_exact_dose_without_source_dose_keeps_guidance_and_hands_off(self):
        evidence = _result(_row(
            "Dạ giai đoạn trái non nên dùng NPK cân đối, bổ sung Canxi và Magie. "
            "Nên chia nhỏ lượng bón định kỳ 10-12 ngày/lần.",
        ))
        result = build_grounded_agronomy_guidance(
            query="Nhãn nuôi trái non bón liều lượng bao nhiêu?",
            slots={"crop": "nhãn", "crop_stage": "nuôi trái non"},
            search_result=evidence,
            known_crop_terms=KNOWN_CROPS,
            contacts=CONTACTS,
        )
        self.assertIn("NPK cân đối", result["answer"])
        self.assertIn("chưa có mức kg/gốc", result["answer"])
        self.assertIn("Cao Văn Được", result["answer"])
        self.assertTrue(result["requires_expert"])

    def test_unknown_or_highly_specific_case_is_short_and_uses_both_contacts(self):
        result = build_grounded_agronomy_guidance(
            query="Cây lạ bị triệu chứng chưa có trong cẩm nang",
            slots={"crop": "cây lạ", "symptom": "cháy toàn bộ rễ"},
            search_result={"confidence": "low", "results": []},
            known_crop_terms=KNOWN_CROPS,
            contacts=CONTACTS,
        )
        self.assertIn("chưa có hướng dẫn đủ sát", result["answer"])
        self.assertIn("Lê Thanh Đạm", result["answer"])
        self.assertIn("Cao Văn Được", result["answer"])
        self.assertLess(len(result["answer"]), 500)

    def test_non_agronomy_or_unsourced_rows_are_never_used(self):
        wrong_category = _row("Dạ giá hôm nay là 500.000 đồng.")
        wrong_category["category"] = "sales"
        no_source = _row("Dạ bón 5 kg/gốc.", source="")
        result = build_grounded_agronomy_guidance(
            query="Bón gì?",
            slots={"crop": "ổi"},
            search_result=_result(wrong_category, no_source),
            known_crop_terms=KNOWN_CROPS,
            contacts=CONTACTS,
        )
        self.assertNotIn("500.000", result["answer"])
        self.assertNotIn("5 kg/gốc", result["answer"])
        self.assertEqual(result["source_ids"], [])


class AgronomyRetrievalSpeedTests(unittest.IsolatedAsyncioTestCase):
    async def test_moderate_agronomy_lexical_match_skips_embedding(self):
        original_items = rag_search._knowledge_items.get("cfc")
        original_phrases = rag_search._phrase_map.get("cfc")
        original_intents = rag_search._intent_map.get("cfc")
        try:
            row = {
                "intent": "agronomy_flowering",
                "answer": "Giai đoạn ra hoa cần cân đối Lân và Kali.",
                "category": "agronomy",
                "question_examples": "Cây đang ra hoa nên bón gì",
                "learning_tags": "flowering",
                "audience": "customer",
                "source_id": "test:agronomy",
                "answer_mode": "direct",
                "risk_level": "medium",
            }
            rag_search._knowledge_items["cfc"] = [row]
            rag_search._phrase_map["cfc"] = {}
            rag_search._intent_map["cfc"] = {row["intent"]: row}
            embed = AsyncMock(return_value=[0.0])
            with patch("rag_search._ensure_cache_loaded", new=AsyncMock()), \
                    patch("rag_search.embed_text", new=embed):
                result = await rag_search.semantic_search(
                    "Cây ổi đang ra hoa hay rụng bông thì nên bón gì",
                    "cfc",
                    category_filter="agronomy",
                )
            self.assertEqual(result["intent"], "agronomy_flowering")
            self.assertEqual(result["retrieval_method"], "in_memory_lexical")
            embed.assert_not_awaited()
        finally:
            rag_search._knowledge_items["cfc"] = original_items or []
            rag_search._phrase_map["cfc"] = original_phrases or {}
            rag_search._intent_map["cfc"] = original_intents or {}


if __name__ == "__main__":
    unittest.main()
