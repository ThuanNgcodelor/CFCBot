"""
domains.customers.routes — FastAPI Router cho Customer Conversations và Leads CRM.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from .schemas import CustomerUpdateRequest
from .service import (
    get_customers_list,
    get_customer_session_detail,
    update_customer_profile,
    delete_customer_data,
    reset_customer_chat_session,
    get_customer_chat_history,
    export_customers_to_csv_data,
)

router = APIRouter(prefix="/customers", tags=["Customers & Leads CRM"])


@router.get("")
async def list_customers_endpoint(brand: str = Query("all"), page: int = 1, page_size: int = 20):
    """Danh sách khách hàng và thông tin profile."""
    return await get_customers_list(brand=brand, page=page, page_size=page_size)


@router.get("/export")
async def export_customers_csv_endpoint(
    brand: str = Query("all"),
    has_phone: Optional[bool] = None,
    lead_stage: Optional[str] = None,
):
    """Xuất danh sách khách hàng ra file CSV."""
    csv_content = await export_customers_to_csv_data(brand=brand, has_phone=has_phone, lead_stage=lead_stage)
    filename = f"cfc_ai_customers_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{brand}/{sender_id}/session")
async def get_customer_session_endpoint(brand: str, sender_id: str):
    """Xem session chat của 1 khách."""
    return await get_customer_session_detail(brand=brand, sender_id=sender_id)


@router.put("/{brand}/{sender_id}")
async def update_customer_endpoint(brand: str, sender_id: str, req: CustomerUpdateRequest):
    """Chỉnh sửa thông tin khách hàng (SĐT, Khu vực, Tên, Lead stage, Admin notes)."""
    return await update_customer_profile(brand=brand, sender_id=sender_id, updates=req.dict(exclude_unset=True))


@router.delete("/{brand}/{sender_id}")
async def delete_customer_endpoint(brand: str, sender_id: str):
    """Xóa hoàn toàn hồ sơ và session của khách hàng khỏi Redis."""
    return await delete_customer_data(brand=brand, sender_id=sender_id)


@router.delete("/{brand}/{sender_id}/session")
async def reset_customer_session_endpoint(brand: str, sender_id: str):
    """Reset session chat (giúp bot bắt đầu lại hội thoại)."""
    return await reset_customer_chat_session(brand=brand, sender_id=sender_id)


@router.get("/{brand}/{sender_id}/history")
async def get_customer_history_endpoint(brand: str, sender_id: str):
    """Lấy toàn bộ lịch sử hội thoại của 1 khách hàng từ Redis."""
    return await get_customer_chat_history(brand=brand, sender_id=sender_id)
