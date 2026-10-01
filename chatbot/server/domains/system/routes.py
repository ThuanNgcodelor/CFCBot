"""
domains.system.routes — FastAPI Router cho System, Settings, Status và Analytics.
"""

from fastapi import APIRouter, HTTPException
from domains.common.config import get_cfg, save_settings
from .schemas import SettingsUpdateRequest, TelegramTestRequest
from .service import (
    get_system_status,
    get_stats_today,
    get_weekly_analytics,
    save_daily_snapshot,
    test_telegram_connection,
)

router = APIRouter(tags=["System & Settings"])


@router.get("/settings")
async def get_settings_endpoint():
    """Lấy cấu hình hiện tại để hiển thị trên giao diện Cài đặt."""
    return get_cfg()


@router.post("/settings")
async def update_settings_endpoint(req: SettingsUpdateRequest):
    """Lưu cấu hình API keys và kết nối trực tiếp từ giao diện Admin."""
    current_cfg = get_cfg()

    if req.redis:
        current_cfg.setdefault("redis", {}).update(req.redis)
    if req.ollama:
        current_cfg.setdefault("ollama", {}).update(req.ollama)
    if req.n8n:
        current_cfg.setdefault("n8n", {}).update(req.n8n)
    if req.rag:
        current_cfg.setdefault("rag", {}).update(req.rag)
    if req.ai_providers:
        current_cfg.setdefault("ai_providers", {}).update(req.ai_providers)
    if req.telegram:
        current_cfg.setdefault("telegram", {}).update(req.telegram)
    if req.shopee:
        current_cfg.setdefault("shopee", {}).update(req.shopee)

    updated = save_settings(current_cfg)
    return {
        "success": True,
        "message": "Đã lưu cài đặt và API keys thành công!",
        "settings": updated,
    }


@router.get("/status")
async def system_status_endpoint():
    """Trạng thái tất cả dịch vụ: Redis, Ollama, n8n, Python API."""
    return await get_system_status()


@router.get("/stats/today")
async def stats_today_endpoint():
    """Thống kê hôm nay: số khách, brand, lead stage, intent phổ biến."""
    return await get_stats_today()


@router.get("/analytics/weekly")
async def analytics_weekly_endpoint():
    """Dữ liệu phân tích 7 ngày gần nhất."""
    return await get_weekly_analytics()


@router.post("/analytics/snapshot")
async def analytics_snapshot_endpoint():
    """Chụp snapshot thống kê hôm nay vào Redis."""
    return await save_daily_snapshot()


@router.post("/telegram/test")
async def telegram_test_endpoint(req: TelegramTestRequest):
    """Kiểm tra gửi tin nhắn Telegram."""
    bot_token = req.bot_token or get_cfg().get("telegram", {}).get("bot_token", "")
    chat_id = req.chat_id or get_cfg().get("telegram", {}).get("chat_id", "")
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Thiếu Bot Token hoặc Chat ID")

    res = await test_telegram_connection(bot_token=bot_token, chat_id=chat_id, message=req.message or "")
    return res
