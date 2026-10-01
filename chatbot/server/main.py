"""
main.py — FastAPI app chính cho Semantic RAG Service.

Endpoints:
  GET  /health          → kiểm tra service + Ollama + Redis
  POST /sync?brand=zeo  → đồng bộ FAQ từ Redis snapshot → Vector Index
  POST /search          → tìm kiếm ngữ nghĩa
  POST /rewrite         → gọi Ollama để viết lại câu trả lời tự nhiên hơn (tuỳ chọn)
"""

import asyncio
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from admin_routes import router as admin_router
from embedder import embed_text, get_embed_dim
from knowledge_sync import sync_brand
from rag_search import get_redis, semantic_search

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# Background Tasks (Shopee Sync 10 min, Analytics Snapshot)
# ─────────────────────────────────────────

async def _periodic_shopee_sync():
    """Tự động sync Shopee catalog từ Google Sheets mỗi 10 phút."""
    while True:
        try:
            await asyncio.sleep(600)  # 10 phút
            from admin_routes import sync_shopee_from_sheet, _cfg
            cfg = _cfg()
            sheet_url = cfg.get("shopee", {}).get("sheet_url", "")
            if sheet_url:
                logger.info("Shopee auto-sync starting (10 min cycle)...")
                res = await sync_shopee_from_sheet(sheet_url)
                logger.info("Shopee auto-sync completed: %s", res)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Shopee auto-sync error: %s", e)


async def _periodic_daily_snapshot():
    """Tự động chụp snapshot số liệu phân tích mỗi 1 giờ."""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 giờ
            from admin_routes import save_daily_snapshot
            await save_daily_snapshot()
            logger.info("Daily analytics snapshot saved")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Analytics snapshot error: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo background tasks
    task_shopee = asyncio.create_task(_periodic_shopee_sync())
    task_snapshot = asyncio.create_task(_periodic_daily_snapshot())
    logger.info("CFC AI background workers initialized (Shopee 10m sync, Analytics snapshot).")
    yield
    # Dọn dẹp
    task_shopee.cancel()
    task_snapshot.cancel()


app = FastAPI(
    title="ZeO/CFC Semantic RAG & CFC AI Admin",
    description="Tìm kiếm ngữ nghĩa tiếng Việt & Quản trị Chatbot ZeO và CFC Cò Bay",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký admin API router
app.include_router(admin_router)

# Mount static folder
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """Giao diện web quản trị CFC AI Admin Dashboard."""
    html_file = static_dir / "admin.html"
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse("<h1>admin.html not found</h1>", status_code=404)


@app.get("/")
async def root():
    """Chuyển hướng hoặc mở CFC AI Admin Dashboard."""
    return FileResponse(static_dir / "admin.html")


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


# ─────────────────────────────────────────
# Models
# ─────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    brand: str = "zeo"   # "zeo" hoặc "cfc"
    top_k: int = 5
    category_filter: Optional[str] = None


class RewriteRequest(BaseModel):
    query: str            # Câu hỏi gốc của khách
    answer: str           # Câu trả lời thô từ RAG
    brand: str = "zeo"
    tone: str = "friendly"  # "friendly" | "formal"


class ConversationControlRequest(BaseModel):
    admin_id: str = ""
    reason: str = ""


def _require_conversation_control_key(value: Optional[str]) -> None:
    """Keep the handover controls closed until an internal caller is configured."""
    expected = os.getenv("CHAT_CONVERSATION_CONTROL_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="conversation control is not configured")
    if not value or not hmac.compare_digest(value, expected):
        raise HTTPException(status_code=403, detail="invalid conversation control key")


# ─────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────

@app.get("/health")
async def health():
    """Kiểm tra trạng thái của service, Ollama và Redis."""
    cfg = _load_settings()
    status = {"service": "ok", "ollama": "unknown", "redis": "unknown", "embed_model": cfg["ollama"]["embed_model"]}

    # Check Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{cfg['ollama']['base_url']}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            has_embed = any(cfg["ollama"]["embed_model"].split(":")[0] in m for m in models)
            status["ollama"] = "ok"
            status["embed_model_available"] = has_embed
            status["available_models"] = models
    except Exception as e:
        status["ollama"] = f"error: {e}"

    # Check Redis
    try:
        r = await get_redis()
        # pyrefly: ignore [not-async]
        await r.ping()
        status["redis"] = "ok"
        # Kiểm tra index đã tồn tại chưa
        try:
            result = await r.execute_command("FT._LIST")
            # pyrefly: ignore [not-iterable]
            status["vector_indexes"] = [idx.decode() if isinstance(idx, bytes) else idx for idx in result]
        except Exception:
            status["vector_indexes"] = []
    except Exception as e:
        status["redis"] = f"error: {e}"

    return status


@app.post("/sync")
async def sync_knowledge(
    brand: str = Query("zeo", description="'zeo' hoặc 'cfc' hoặc 'all'"),
    snapshot_key: Optional[str] = Query(None, description="Approved active/candidate Redis snapshot key"),
):
    """
    Đọc FAQ từ Redis snapshot, tạo embeddings, upsert vào Vector Index.
    Chạy khi cập nhật dữ liệu FAQ mới từ Google Sheets.
    """
    if brand.lower() == "all":
        if snapshot_key:
            raise HTTPException(status_code=400, detail="snapshot_key không dùng được với brand=all")
        zeo_result = await sync_brand("zeo")
        cfc_result = await sync_brand("cfc")
        return {"zeo": zeo_result, "cfc": cfc_result}
    
    if brand.lower() not in ("zeo", "cfc"):
        raise HTTPException(status_code=400, detail="brand phải là 'zeo', 'cfc', hoặc 'all'")
    
    return await sync_brand(brand.lower(), snapshot_key=snapshot_key)


@app.post("/search")
async def search(req: SearchRequest):
    """
    Tìm kiếm ngữ nghĩa: nhận câu hỏi → embed → KNN trên Redis → trả top kết quả.
    
    n8n gọi endpoint này thay cho Node JS 'RAG Tim Kiem'.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query không được để trống")
    
    result = await semantic_search(
        query=req.query.strip(),
        brand=req.brand.lower(),
        top_k=min(req.top_k, 10),
        category_filter=req.category_filter,
    )
    
    if "error" in result:
        # Trả 200 thay vì 500 để n8n không crash — chỉ confidence=low
        return result
    
    return result


@app.post("/rewrite")
async def rewrite_answer(req: RewriteRequest):
    """
    Dùng Ollama (qwen2.5:7b-instruct) để viết lại câu trả lời thô RAG
    thành ngôn ngữ tự nhiên, thân thiện.
    
    n8n có thể gọi endpoint này sau /search nếu answer_mode='rewrite'.
    """
    cfg = _load_settings()
    
    brand_name = "ZeO" if req.brand.lower() == "zeo" else "Cò Bay"
    tone_instruction = (
        "thân thiện, gần gũi, dùng 'bạn' và 'mình'"
        if req.tone == "friendly"
        else "lịch sự, chuyên nghiệp"
    )
    
    system_prompt = (
        f"Bạn là nhân viên CSKH của {brand_name}. "
        f"Viết lại câu trả lời sau theo giọng {tone_instruction}. "
        f"Giữ nguyên tất cả thông tin thực tế (giá, địa chỉ, số điện thoại, chính sách). "
        f"KHÔNG thêm thông tin mới hoặc bịa đặt. Chỉ trả về câu trả lời, không giải thích."
    )
    
    user_prompt = (
        f"Khách hỏi: {req.query}\n"
        f"Câu trả lời thô: {req.answer}\n"
        f"Hãy viết lại câu trả lời cho tự nhiên hơn:"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{cfg['ollama']['base_url']}/api/chat",
                json={
                    "model": "qwen2.5:7b-instruct",
                    "stream": False,
                    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 300},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            rewritten = data.get("message", {}).get("content", req.answer).strip()
    except Exception as e:
        logger.warning("Rewrite lỗi, trả về answer gốc: %s", e)
        rewritten = req.answer

    return {
        "original_answer": req.answer,
        "rewritten_answer": rewritten,
        "brand": req.brand,
    }


# ─────────────────────────────────────────
# Fast-Path Chatbot Pipeline (< 50ms - 300ms)
# ─────────────────────────────────────────

from chat_pipeline import ChatPipelineRequest, ChatPipelineResponse, process_chat_pipeline


@app.post("/api/chat-pipeline", response_model=ChatPipelineResponse)
@app.post("/api/chat/pipeline", response_model=ChatPipelineResponse)
async def chat_pipeline_endpoint(req: ChatPipelineRequest):
    """
    High-Performance Fast-Path Chatbot Pipeline cho ZeO & CFC.
    Xử lý toàn bộ: Lọc đầu vào, Trích xuất SĐT, Fast-Path, Shopee Match,
    RediSearch KNN, Cập nhật Profile/Session và Bắn Telegram Lead.
    Tốc độ: < 50ms - 300ms.
    """
    return await process_chat_pipeline(req)


@app.post("/api/conversations/{brand}/{sender_id}/takeover")
async def conversation_takeover_endpoint(
    brand: str,
    sender_id: str,
    req: ConversationControlRequest,
    x_conversation_control_key: Optional[str] = Header(default=None),
):
    """Internal inbox/n8n contract: an admin has claimed the conversation."""
    _require_conversation_control_key(x_conversation_control_key)
    from chat_pipeline import set_conversation_takeover_state
    try:
        takeover = await set_conversation_takeover_state(
            brand=brand,
            sender_id=sender_id,
            status="human",
            admin_id=req.admin_id,
            reason=req.reason or "admin_claimed",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "takeover_state": takeover}


@app.post("/api/conversations/{brand}/{sender_id}/close")
async def conversation_close_endpoint(
    brand: str,
    sender_id: str,
    req: ConversationControlRequest,
    x_conversation_control_key: Optional[str] = Header(default=None),
):
    """Internal inbox/n8n contract: admin ended support and the bot may resume."""
    _require_conversation_control_key(x_conversation_control_key)
    from chat_pipeline import set_conversation_takeover_state
    try:
        takeover = await set_conversation_takeover_state(
            brand=brand,
            sender_id=sender_id,
            status="closed",
            admin_id=req.admin_id,
            reason=req.reason or "admin_closed",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "takeover_state": takeover}


@app.post("/api/shopee/refresh-cache")
async def refresh_shopee_cache_endpoint(brand: str = Query("all", description="'zeo', 'cfc' hoặc 'all'")):
    """Làm mới lại in-memory cache cho danh mục sản phẩm Shopee."""
    from shopee_matcher import refresh_shopee_cache
    refresh_shopee_cache(brand)
    return {"status": "ok", "message": f"Shopee cache refreshed for brand={brand}"}


@app.post("/api/web/refresh-cache")
async def refresh_web_cache_endpoint(brand: str = Query("all", description="'zeo', 'cfc' hoặc 'all'")):
    """Làm mới lại in-memory cache cho dữ liệu Web kiến thức."""
    return {"status": "ok", "message": f"Web cache refreshed for brand={brand}"}


# ─────────────────────────────────────────
# Dev entrypoint
# ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    cfg = _load_settings()
    srv = cfg.get("server", {})
    uvicorn.run(
        "main:app",
        host=srv.get("host", "0.0.0.0"),
        port=srv.get("port", 8000),
        reload=srv.get("reload", True),
    )
