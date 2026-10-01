"""
domains.n8n.routes — FastAPI Router cho n8n Automation và Workflows.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket
from .schemas import DeployRequest
from .service import (
    get_n8n_workflows_list,
    toggle_n8n_workflow_state,
    get_n8n_executions_list,
    get_workflow_executions_paginated,
    get_workflow_detail_data,
    get_n8n_file_status_data,
    deploy_workflow_code,
    get_n8n_deploy_log_history,
    handle_file_watch_ws,
)

router = APIRouter(prefix="/n8n", tags=["n8n Automation & Workflows"])


@router.get("/workflows")
async def list_workflows_endpoint():
    """Danh sách workflow n8n và trạng thái active."""
    return await get_n8n_workflows_list()


@router.post("/workflows/{workflow_id}/toggle")
async def toggle_workflow_endpoint(workflow_id: str):
    """Bật hoặc tắt một workflow."""
    res = await toggle_n8n_workflow_state(workflow_id)
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 500), detail=res["error"])
    return res


@router.get("/executions")
async def list_executions_endpoint(limit: int = Query(20, le=50)):
    """Lịch sử chạy workflow gần nhất."""
    return await get_n8n_executions_list(limit=limit)


@router.post("/sync-knowledge")
async def sync_knowledge_endpoint(
    brand: str = Query("all"),
    snapshot_key: Optional[str] = Query(None),
):
    """Trigger đồng bộ Knowledge từ Google Sheets lên Redis + Vector Index."""
    from knowledge_sync import sync_brand
    if brand == "all":
        if snapshot_key:
            raise HTTPException(status_code=400, detail="snapshot_key is not supported with brand=all")
        zeo = await sync_brand("zeo")
        cfc = await sync_brand("cfc")
        return {"zeo": zeo, "cfc": cfc}
    return await sync_brand(brand, snapshot_key=snapshot_key)


@router.get("/workflows/{workflow_id}/executions")
async def list_workflow_executions_endpoint(
    workflow_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=5, le=100),
    status: str = Query("all"),
):
    """Lịch sử execution của 1 workflow, có phân trang và filter trạng thái."""
    return await get_workflow_executions_paginated(workflow_id, page=page, limit=limit, status=status)


@router.get("/workflows/{workflow_id}/detail")
async def workflow_detail_endpoint(workflow_id: str):
    """Chi tiết workflow: node count, tags, updatedAt, active status."""
    res = await get_workflow_detail_data(workflow_id)
    if "error" in res:
        raise HTTPException(status_code=res.get("status_code", 500), detail=res["error"])
    return res


@router.get("/file-status")
async def file_status_endpoint():
    """Kiểm tra file .ts local có thay đổi chưa push lên n8n không."""
    return await get_n8n_file_status_data()


@router.post("/deploy")
async def deploy_workflow_endpoint(req: DeployRequest):
    """Deploy workflow lên n8n bằng n8nac push."""
    res = await deploy_workflow_code(req.workflow_file, auto_resolve_conflict=req.auto_resolve_conflict)
    if not res.get("ok"):
        raise HTTPException(status_code=res.get("status_code", 500), detail=res)
    return res


@router.get("/deploy-log")
async def deploy_log_endpoint():
    """Lịch sử các lần deploy workflow gần nhất."""
    return await get_n8n_deploy_log_history()


@router.websocket("/ws/file-watch")
async def ws_file_watch_endpoint(websocket: WebSocket):
    """WebSocket push thông báo real-time khi file .ts thay đổi."""
    await handle_file_watch_ws(websocket)
