"""
domains.assistant.routes — FastAPI Router cho AI Executive Assistant.
"""

from fastapi import APIRouter, HTTPException
from .schemas import AssistantChatRequest
from .service import get_quick_prompts_list

router = APIRouter(prefix="/assistant", tags=["AI Executive Assistant"])


@router.post("/chat")
async def assistant_chat_endpoint(req: AssistantChatRequest):
    """Trò chuyện trực tiếp với AI Assistant để điều khiển n8n và tổng hợp số liệu."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Tin nhắn không được để trống")

    from ai_engine import run_assistant_agent_chat
    res = await run_assistant_agent_chat(
        user_message=req.message.strip(),
        history=req.history,
        brand=req.brand or "all"
    )
    return res


@router.get("/quick-prompts")
async def assistant_quick_prompts_endpoint():
    """Danh sách các câu hỏi gợi ý nhanh cho Trợ lý điều hành."""
    return {"prompts": get_quick_prompts_list()}
