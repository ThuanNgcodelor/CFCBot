"""
domains.learning.routes — FastAPI Router cho Learning Queue và AI Tự Học.
"""

from fastapi import APIRouter, HTTPException, Query
from .schemas import ApproveRequest
from .service import (
    fetch_learning_queue_items,
    dismiss_learning_queue_item,
    approve_and_add_faq_item,
    suggest_answers_for_learning_queue,
)

router = APIRouter(tags=["Learning Queue & FAQ"])


@router.get("/learning-queue")
async def get_learning_queue_endpoint(brand: str = Query("all"), limit: int = 50):
    """Lấy danh sách câu hỏi bot chưa chắc / khách phàn nàn để review."""
    return await fetch_learning_queue_items(brand=brand, limit=limit)


@router.post("/learning-queue/dismiss")
async def dismiss_queue_item_endpoint(brand: str = Query(...), queue_key: str = Query(...), raw_value: str = Query(...)):
    """Xóa 1 item khỏi learning queue (bỏ qua)."""
    ok = await dismiss_learning_queue_item(queue_key=queue_key, raw_value=raw_value)
    return {"success": ok}


@router.post("/learning-queue/approve")
# pyrefly: ignore [bad-function-definition]
async def approve_and_add_to_faq_endpoint(brand: str = Query(...), req: ApproveRequest = ...):
    """Duyệt 1 câu từ Learning Queue → thêm vào Redis KB snapshot + re-sync vector."""
    return await approve_and_add_faq_item(brand=brand, req_data=req.dict())


@router.post("/learning/ai-suggest")
async def ai_suggest_from_learning_queue_endpoint(brand: str = Query("all")):
    """AI tự phân tích Learning Queue: gom nhóm câu tương tự + đề xuất intent + câu trả lời."""
    return await suggest_answers_for_learning_queue(brand=brand)
