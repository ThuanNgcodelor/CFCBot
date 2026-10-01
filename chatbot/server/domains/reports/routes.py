"""
domains.reports.routes — FastAPI Router cho AI Executive Briefing Reports.
"""

from fastapi import APIRouter
from ai_reporter import get_latest_report, generate_daily_executive_report

router = APIRouter(prefix="/reports", tags=["AI Executive Reports"])


@router.get("/latest")
async def get_latest_report_endpoint():
    """Lấy bản tin báo cáo kinh doanh gần nhất đã lưu trong Redis."""
    report = await get_latest_report()
    return {"has_report": report is not None, "report": report}


@router.post("/generate")
async def generate_report_endpoint(send_telegram: bool = False):
    """Kích hoạt AI quét dữ liệu và tạo Bản Tin Báo Cáo Điều Hành mới."""
    res = await generate_daily_executive_report(send_telegram=send_telegram)
    return res
