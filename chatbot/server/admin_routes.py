"""
admin_routes.py — Facade Router cho CFC AI Admin Dashboard theo mô hình DDD (Domain-Driven Design).

Tất cả các domain nghiệp vụ được bóc tách vào thư mục domains/:
  - domains.system      : Trạng thái hệ thống, Settings, Health & Analytics.
  - domains.assistant   : Trợ lý điều hành AI & Autonomous Tool Agent.
  - domains.customers   : Quản lý khách hàng, hội thoại, Leads CRM & Export CSV.
  - domains.n8n         : Điều khiển Workflow n8n, Executions & Real-time File Watching.
  - domains.reports     : Báo cáo điều hành kinh doanh & AI Insights.
  - domains.learning    : Hàng đợi học (Learning Queue) & AI gợi ý FAQ.
  - domains.knowledge   : Kho tri thức, Tài liệu Markdown & Google Sheets Live Hub.
  - domains.rag_test    : Kiểm thử Semantic Search RAG & NLU evaluation.
"""

from fastapi import APIRouter

from domains.common.config import get_cfg, save_settings, auto_get_redis_env_pass
from domains.common.db import get_redis_client, get_n8n_config, n8n_request
from domains.system import router as system_router, save_daily_snapshot
from domains.assistant import router as assistant_router
from domains.customers import router as customers_router
from domains.n8n import router as n8n_router
from domains.reports import router as reports_router
from domains.learning import router as learning_router
from domains.knowledge import router as knowledge_router, sync_shopee_from_sheet
from domains.rag_test import router as rag_test_router
from domains.amis import router as amis_router

# ── Facade Admin Router ──
router = APIRouter(prefix="/admin", tags=["CFC AI Admin Gateway"])

# Đăng ký toàn bộ Domain Routers vào Gateway
router.include_router(system_router)
router.include_router(assistant_router)
router.include_router(customers_router)
router.include_router(n8n_router)
router.include_router(reports_router)
router.include_router(learning_router)
router.include_router(knowledge_router)
router.include_router(rag_test_router)
router.include_router(amis_router)


# ── Backward-Compatible Re-exports cho các module bên ngoài (main.py, ai_agent_tools.py) ──
_cfg = get_cfg
_get_redis = get_redis_client
_n8n_cfg = get_n8n_config
_auto_get_redis_env_pass = auto_get_redis_env_pass

__all__ = [
    "router",
    "_cfg",
    "_get_redis",
    "_n8n_cfg",
    "_auto_get_redis_env_pass",
    "save_daily_snapshot",
    "sync_shopee_from_sheet",
]
