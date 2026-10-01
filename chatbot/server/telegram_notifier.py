"""
telegram_notifier.py — Module Bắn Thông Báo Lead & Báo Cáo Tức Thì Qua Telegram
Chức năng:
  1. Gửi thông báo Lead (SĐT, Địa chỉ, Nhu cầu, Tên khách) vào Telegram cá nhân / Group Sale ngay khi có khách để lại thông tin.
  2. Gửi bản tin Báo cáo Kinh doanh AI hàng ngày vào Telegram.
  3. Kiểm tra kết nối Bot Telegram qua API.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

from evaluation_safety import external_side_effects_allowed

logger = logging.getLogger(__name__)

_settings: dict = {}


def _load_settings() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _settings


def _telegram_cfg() -> dict:
    return _load_settings().get("telegram", {
        "enabled": False,
        "bot_token": "",
        "chat_id": "",
    })


async def send_telegram_message(
    text: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: str = "HTML",
) -> dict:
    """Gửi tin nhắn bất kỳ qua Telegram Bot API."""
    if not external_side_effects_allowed():
        return {
            "success": False,
            "skipped": True,
            "reason": "EVALUATION_EXTERNAL_SIDE_EFFECT_BLOCKED",
        }
    cfg = _telegram_cfg()
    token = bot_token or cfg.get("bot_token", "")
    target_chat = chat_id or cfg.get("chat_id", "")

    if not token or not target_chat:
        return {"success": False, "error": "Chưa cấu hình Telegram bot_token hoặc chat_id"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return {"success": True, "message_id": data.get("result", {}).get("message_id")}
            return {"success": False, "error": data.get("description", "Lỗi gửi tin nhắn Telegram")}
    except Exception as e:
        logger.warning("Lỗi kết nối Telegram API: %s", e)
        return {"success": False, "error": str(e)}


async def notify_new_lead(
    brand: str,
    phone: str,
    area: str = "",
    fb_name: str = "",
    need: str = "",
    sender_id: str = "",
) -> dict:
    """Bắn thông báo Lead mới (Khách có SĐT) vào Telegram."""
    cfg = _telegram_cfg()
    if not cfg.get("enabled", True) and not cfg.get("bot_token"):
        return {"success": False, "skipped": True, "reason": "Telegram chưa kích hoạt"}

    now_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    brand_title = "ZEO VIETNAM 🧴" if brand.upper() == "ZEO" else "CFC CÒ BAY 🌾"

    msg = f"""
🚨 <b>CÓ LEAD KHÁCH HÀNG MỚI ({brand_title})</b>

👤 <b>Khách hàng:</b> {fb_name or 'Khách Messenger'}
📞 <b>Số điện thoại:</b> <code>{phone}</code> (👉 <a href="tel:{phone}">Bấm để gọi</a>)
📍 <b>Khu vực/Địa chỉ:</b> {area or 'Chưa cung cấp'}
🎯 <b>Nhu cầu / Intent:</b> {need or 'Tư vấn sản phẩm / Đặt hàng'}
🆔 <b>Sender ID:</b> <code>{sender_id}</code>
⏰ <b>Thời gian:</b> {now_str}

<i>(Dữ liệu được đồng bộ từ CFC AI Chatbot Hub)</i>
""".strip()

    return await send_telegram_message(msg)


async def notify_admin_unanswered(
    brand: str,
    query: str,
    sender_id: str = "",
    score: float = 0.0,
) -> dict:
    """Bắn cảnh báo câu hỏi chưa có câu trả lời (score thấp) để Admin hỗ trợ ngay."""
    cfg = _telegram_cfg()
    if not cfg.get("enabled", True) and not cfg.get("bot_token"):
        return {"success": False, "skipped": True, "reason": "Telegram chưa kích hoạt"}

    now_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    brand_title = "ZEO VIETNAM 🧴" if brand.upper() == "ZEO" else "CFC CÒ BAY 🌾"

    msg = f"""
⚠️ <b>CẦN ADMIN HỖ TRỢ — BOT KHÔNG TỰ TIN ({brand_title})</b>

❓ <b>Khách hỏi:</b> <i>"{query}"</i>
📊 <b>RAG Score:</b> {round(score * 100)}% (Dưới ngưỡng 55%)
🆔 <b>Sender ID:</b> <code>{sender_id or 'Ẩn danh / Web Test'}</code>
⏰ <b>Thời gian:</b> {now_str}

👉 <i>Vui lòng vào fanpage hoặc Learning Queue để trả lời và bổ sung FAQ!</i>
""".strip()

    return await send_telegram_message(msg)


async def notify_urgent_complaint(
    brand: str,
    query: str,
    phone: str = "",
    sender_id: str = "",
    fb_name: str = "",
) -> dict:
    """Bắn cảnh báo khiếu nại / hàng lỗi / bể vỡ khẩn cấp cho Admin."""
    cfg = _telegram_cfg()
    if not cfg.get("enabled", True) and not cfg.get("bot_token"):
        return {"success": False, "skipped": True, "reason": "Telegram chưa kích hoạt"}

    now_str = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
    brand_title = "ZEO VIETNAM" if brand.upper() == "ZEO" else "CFC CÒ BAY"

    msg = f"""
🚨 <b>KHIẾU NẠI / HÀNG LỖI CẦN XỬ LÝ GẤP ({brand_title})</b>

👤 <b>Khách hàng:</b> {fb_name or 'Khách Messenger'}
📞 <b>Số điện thoại:</b> {phone or 'Đang yêu cầu khách cung cấp'}
💬 <b>Nội dung phản ánh:</b> <i>"{query}"</i>
🆔 <b>Sender ID:</b> <code>{sender_id or 'Ẩn danh'}</code>
⏰ <b>Thời gian:</b> {now_str}

👉 <i>CSKH vui lòng kiểm tra hộp thư Messenger để đổi trả / hoàn tiền ngay cho khách!</i>
""".strip()

    return await send_telegram_message(msg)


async def test_telegram(bot_token: str, chat_id: str) -> dict:
    """Gửi tin nhắn kiểm thử kết nối Telegram."""
    test_msg = "⚡ <b>CFC AI Test Notification</b>\n\nKết nối Telegram Bot thành công! Bạn sẽ nhận được thông báo Lead và Báo cáo tại đây."
    return await send_telegram_message(test_msg, bot_token=bot_token, chat_id=chat_id)
