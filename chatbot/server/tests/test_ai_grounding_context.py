import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from ai_engine import (  # noqa: E402
    consult_cfc_agronomy_with_ai,
    synthesize_cskh_answer,
    validate_grounded_rewrite,
)
from chat_pipeline import _sanitized_chat_history  # noqa: E402


class AiGroundingContextTests(unittest.IsolatedAsyncioTestCase):
    def test_pipeline_history_redacts_pii_and_keeps_roles(self):
        history = _sanitized_chat_history({
            "recent_turns": [{
                "user": "Số mình 0908776655, email test@example.com",
                "bot": "Mình đã nhận số 0908776655",
            }]
        })
        rendered = " ".join(item["content"] for item in history)
        self.assertNotIn("0908776655", rendered)
        self.assertNotIn("test@example.com", rendered)
        self.assertIn("[PHONE]", rendered)
        self.assertIn("[EMAIL]", rendered)
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])

    async def test_synthesis_uses_history_without_default_product_link_or_freeship_claim(self):
        generator = AsyncMock(return_value={
            "success": True,
            "text": "Dạ đây là câu trả lời đã đối chiếu dữ liệu thực tế cho bạn ạ.",
        })
        with patch("ai_engine._load_settings", return_value={
            "grounding_policy": {"customer_fact_generation_mode": "grounded_rewrite"},
        }), patch("ai_engine.generate_ai_text", generator):
            answer = await synthesize_cskh_answer(
                user_query="Loại đó dùng sao?",
                brand="zeo",
                retrieved_facts="Sử dụng theo hướng dẫn trên bao bì.",
                chat_history=[{
                    "role": "user",
                    "content": "Gọi mình theo số 0908776655, mail test@example.com",
                }],
                catalog_products=[{"name": "Sản phẩm thử", "price": "100000"}],
            )

        self.assertIsNotNone(answer)
        prompt = generator.await_args.kwargs["prompt"]
        system_prompt = generator.await_args.kwargs["system_prompt"]
        self.assertNotIn("0908776655", prompt)
        self.assertNotIn("test@example.com", prompt)
        self.assertIn("[PHONE]", prompt)
        self.assertNotIn("shopee.vn/zeovietnamofficial", prompt)
        self.assertNotIn("Freeship Extra toàn quốc", system_prompt)
        self.assertNotIn("preferred_provider", generator.await_args.kwargs)

    def test_grounded_rewrite_accepts_supported_agronomy_facts(self):
        facts = (
            "Sầu riêng giai đoạn nuôi trái non cần cân đối Kali và Canxi-Bo, tránh dư Đạm. "
            "Cẩm nang chưa có mức kg/gốc cho trường hợp này. "
            "Trao đổi trực tiếp với Khuyến nông Lê Thanh Đạm 0353 857 516."
        )
        candidate = (
            "Dạ với sầu riêng đang nuôi trái non, mình nên cân đối Kali và Canxi-Bo, "
            "đồng thời tránh dư Đạm. Cẩm nang chưa có mức kg/gốc cụ thể; bạn có thể "
            "trao đổi với anh Lê Thanh Đạm qua số 0353 857 516 để được kiểm tra sát vườn ạ."
        )
        self.assertEqual(validate_grounded_rewrite(candidate, facts), (True, "GROUNDED_REWRITE_VALID"))

    def test_grounded_rewrite_rejects_invented_dose(self):
        facts = "Sầu riêng giai đoạn nuôi trái non cần cân đối Kali; chưa có mức kg/gốc."
        candidate = "Dạ bạn bón 2 kg/gốc, lặp lại sau 10 ngày để nuôi trái non ạ."
        valid, reason = validate_grounded_rewrite(candidate, facts)
        self.assertFalse(valid)
        self.assertEqual(reason, "UNSUPPORTED_QUANTITY")

    def test_grounded_rewrite_rejects_invented_commercial_claim(self):
        facts = "Công ty có sản phẩm NPK 20-20-15 bao 25kg."
        candidate = "Dạ sản phẩm đang còn hàng và được miễn phí vận chuyển toàn quốc ạ."
        valid, reason = validate_grounded_rewrite(candidate, facts)
        self.assertFalse(valid)
        self.assertIn(reason, {"UNSUPPORTED_INVENTORY", "UNSUPPORTED_SHIPPING"})

    async def test_synthesis_does_not_call_generator_without_grounded_input(self):
        generator = AsyncMock(return_value={"success": True, "text": "Nội dung tự sinh"})
        with patch("ai_engine._load_settings", return_value={
            "grounding_policy": {"customer_fact_generation_mode": "grounded_rewrite"},
        }), patch("ai_engine.generate_ai_text", generator):
            answer = await synthesize_cskh_answer(
                user_query="Phân này có chống mặn tuyệt đối không?",
                brand="cfc",
                retrieved_facts="",
                catalog_products=[],
            )

        self.assertIsNone(answer)
        generator.assert_not_awaited()

    async def test_synthesis_restores_verbatim_uncertainty_before_accepting_rewrite(self):
        generator = AsyncMock(return_value={
            "success": True,
            "text": "Dạ với sầu riêng nuôi trái non, mình nên cân đối Kali và Canxi-Bo, tránh dư Đạm ạ.",
        })
        facts = (
            "Cẩm nang hiện chưa có mức kg/gốc cho trường hợp này. "
            "Sầu riêng nuôi trái non cần cân đối Kali và Canxi-Bo, tránh dư Đạm."
        )
        with patch("ai_engine._load_settings", return_value={
            "grounding_policy": {"customer_fact_generation_mode": "grounded_rewrite"},
        }), patch("ai_engine.generate_ai_text", generator):
            answer = await synthesize_cskh_answer(
                user_query="Liều bao nhiêu một gốc?",
                brand="cfc",
                retrieved_facts=facts,
            )

        self.assertIsNotNone(answer)
        self.assertTrue(answer.startswith("Dạ cẩm nang hiện chưa có mức kg/gốc"))

    async def test_direct_only_mode_skips_even_grounded_rewrite(self):
        generator = AsyncMock(return_value={"success": True, "text": "Nội dung rewrite"})
        with patch("ai_engine._load_settings", return_value={
            "grounding_policy": {"customer_fact_generation_mode": "direct_only"},
        }), patch("ai_engine.generate_ai_text", generator):
            answer = await synthesize_cskh_answer(
                user_query="Dùng sao?",
                brand="zeo",
                retrieved_facts="Dùng theo hướng dẫn trên nhãn.",
            )

        self.assertIsNone(answer)
        generator.assert_not_awaited()

    async def test_deprecated_agronomy_generator_is_fail_closed(self):
        generator = AsyncMock(return_value={"success": True, "text": "Phác đồ tự sinh"})
        with patch("ai_engine.generate_ai_text", generator):
            answer = await consult_cfc_agronomy_with_ai(
                "Sầu riêng nên bón gì?",
                {"crop": "sầu riêng"},
            )
        self.assertIsNone(answer)
        generator.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
