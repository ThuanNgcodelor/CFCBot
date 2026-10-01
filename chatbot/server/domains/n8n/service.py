"""
domains.n8n.service — Business logic cho n8n Automation, Workflow Deployment và Real-time File Watching.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from fastapi import WebSocket, WebSocketDisconnect
from domains.common.db import get_redis_client, n8n_request

logger = logging.getLogger(__name__)

_WORKFLOW_DIR = Path(__file__).resolve().parents[4] / "workflows" / "local-n8n"
_ws_clients: List[WebSocket] = []


def discover_workflow_files() -> Dict[str, Path]:
    """Quét thư mục workflows/local-n8n/*.ts, trả dict {workflow_id: path}."""
    result = {}
    if not _WORKFLOW_DIR.exists():
        return result
    for ts_file in _WORKFLOW_DIR.glob("*.workflow.ts"):
        content = ts_file.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"@workflow\(\s*\{[^}]*?id\s*:\s*['\"]([^'\"]+)['\"]", content, re.DOTALL)
        if m:
            result[m.group(1)] = ts_file
    return result


async def run_cmd(cmd: list, cwd: str) -> Tuple[int, str, str]:
    """Chạy shell command async, trả về (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    # pyrefly: ignore [bad-return]
    return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


async def get_n8n_workflows_list() -> dict:
    """Lấy danh sách workflows từ n8n REST API."""
    try:
        resp = await n8n_request("GET", "/workflows?limit=50")
        if resp.status_code != 200:
            return {"error": f"n8n trả về {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        workflows = [
            {
                "id": w["id"],
                "name": w["name"],
                "active": w.get("active", False),
                "updatedAt": w.get("updatedAt", ""),
                "tags": [t["name"] for t in w.get("tags", [])],
            }
            for w in data
        ]
        return {"workflows": workflows, "total": len(workflows)}
    except Exception as e:
        return {"error": str(e), "workflows": []}


async def toggle_n8n_workflow_state(workflow_id: str) -> dict:
    """Bật / tắt trạng thái active của một workflow."""
    resp = await n8n_request("GET", f"/workflows/{workflow_id}")
    if resp.status_code != 200:
        return {"error": "Workflow không tìm thấy", "status_code": 404}
    wf = resp.json()
    is_active = wf.get("active", False)

    if is_active:
        await n8n_request("POST", f"/workflows/{workflow_id}/deactivate")
    else:
        await n8n_request("POST", f"/workflows/{workflow_id}/activate")

    return {"id": workflow_id, "name": wf.get("name"), "active": not is_active, "changed": True}


async def get_n8n_executions_list(limit: int = 20) -> dict:
    """Lấy danh sách execution gần nhất."""
    try:
        resp = await n8n_request("GET", f"/executions?limit={limit}&status=all")
        if resp.status_code != 200:
            return {"error": f"n8n {resp.status_code}", "data": []}
        data = resp.json().get("data", [])
        executions = [
            {
                "id": e["id"],
                "workflowId": e.get("workflowId"),
                "workflowName": e.get("workflowData", {}).get("name", "?"),
                "status": e.get("status", "?"),
                "startedAt": e.get("startedAt", ""),
                "stoppedAt": e.get("stoppedAt", ""),
            }
            for e in data
        ]
        return {"executions": executions}
    except Exception as e:
        return {"error": str(e), "executions": []}


async def get_workflow_executions_paginated(workflow_id: str, page: int = 1, limit: int = 20, status: str = "all") -> dict:
    """Lấy execution theo từng workflow có lọc và phân trang."""
    try:
        params = f"?workflowId={workflow_id}&limit={limit}&includeData=false"
        if status != "all":
            params += f"&status={status}"
        resp = await n8n_request("GET", f"/executions{params}")
        if resp.status_code != 200:
            return {"error": f"n8n {resp.status_code}", "executions": [], "total": 0}

        data = resp.json()
        all_execs = data.get("data", [])
        total = data.get("count", len(all_execs))

        stats = {"success": 0, "error": 0, "running": 0, "waiting": 0, "other": 0}
        parsed = []
        for e in all_execs:
            st = e.get("status", "other")
            stats[st] = stats.get(st, 0) + 1
            started = e.get("startedAt", "")
            stopped = e.get("stoppedAt", "")
            duration_ms = None
            if started and stopped:
                try:
                    from datetime import datetime as _dt
                    t0 = _dt.fromisoformat(started.replace("Z", "+00:00"))
                    t1 = _dt.fromisoformat(stopped.replace("Z", "+00:00"))
                    duration_ms = int((t1 - t0).total_seconds() * 1000)
                except Exception:
                    pass

            parsed.append({
                "id": e["id"],
                "workflowId": workflow_id,
                "status": st,
                "startedAt": started,
                "stoppedAt": stopped,
                "duration_ms": duration_ms,
                "retryOf": e.get("retryOf"),
                "retrySuccessId": e.get("retrySuccessId"),
            })

        return {
            "executions": parsed,
            "total": total,
            "page": page,
            "limit": limit,
            "stats": stats,
        }
    except Exception as e:
        return {"error": str(e), "executions": [], "total": 0}


async def get_workflow_detail_data(workflow_id: str) -> dict:
    """Lấy chi tiết workflow cấu trúc node và metadata."""
    resp = await n8n_request("GET", f"/workflows/{workflow_id}")
    if resp.status_code != 200:
        return {"error": "Workflow không tìm thấy", "status_code": 404}
    w = resp.json()
    nodes = w.get("nodes", [])
    node_types = {}
    for n in nodes:
        t = n.get("type", "").split(".")[-1]
        node_types[t] = node_types.get(t, 0) + 1
    return {
        "id": w["id"],
        "name": w.get("name"),
        "active": w.get("active", False),
        "updatedAt": w.get("updatedAt"),
        "createdAt": w.get("createdAt"),
        "nodeCount": len(nodes),
        "nodeTypes": node_types,
        "tags": [t["name"] for t in w.get("tags", [])],
        "settings": w.get("settings", {}),
    }


async def get_n8n_file_status_data() -> dict:
    """Kiểm tra thay đổi của các file .ts cục bộ so với n8n cloud."""
    files_info = []
    try:
        wf_map = discover_workflow_files()
        if not wf_map:
            return {"files": [], "note": "Không tìm thấy file .ts trong workflows/local-n8n/"}

        n8n_updated: dict = {}
        try:
            resp = await n8n_request("GET", "/workflows?limit=50")
            if resp.status_code == 200:
                for w in resp.json().get("data", []):
                    raw_ts = w.get("updatedAt", "")
                    if raw_ts:
                        try:
                            n8n_updated[w["id"]] = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                        except Exception:
                            pass
        except Exception:
            pass

        r = get_redis_client()
        redis_push_ts: dict = {}
        for wf_id in wf_map:
            raw = await r.get(f"n8n:deploy:last:{wf_id}")
            if raw:
                try:
                    redis_push_ts[wf_id] = float(raw)
                except Exception:
                    pass

        for wf_id, ts_path in wf_map.items():
            stat = ts_path.stat()
            file_mtime = stat.st_mtime
            file_mtime_dt = datetime.fromtimestamp(file_mtime, tz=timezone.utc)

            if wf_id in n8n_updated:
                n8n_dt = n8n_updated[wf_id]
                has_changes = (file_mtime_dt - n8n_dt).total_seconds() > 60
                baseline_source = "n8n"
                baseline_at = n8n_dt.isoformat()
            elif wf_id in redis_push_ts:
                push_dt = datetime.fromtimestamp(redis_push_ts[wf_id], tz=timezone.utc)
                has_changes = (file_mtime_dt - push_dt).total_seconds() > 60
                baseline_source = "deploy_log"
                baseline_at = push_dt.isoformat()
            else:
                has_changes = False
                baseline_source = "none"
                baseline_at = None

            files_info.append({
                "workflow_id": wf_id,
                "filename": ts_path.name,
                "last_modified": file_mtime_dt.isoformat(),
                "baseline_at": baseline_at,
                "baseline_source": baseline_source,
                "has_changes": has_changes,
            })

    except Exception as e:
        return {"error": str(e), "files": []}
    return {"files": files_info}


async def deploy_workflow_code(workflow_file: str, auto_resolve_conflict: bool = True) -> dict:
    """Deploy file .ts lên n8n server sử dụng n8nac push."""
    r = get_redis_client()
    workspace = str(Path(__file__).resolve().parents[4])
    ts_path = _WORKFLOW_DIR / workflow_file

    if not ts_path.exists():
        return {"error": f"File không tồn tại: {workflow_file}", "status_code": 404}

    wf_map = discover_workflow_files()
    wf_id = next((k for k, v in wf_map.items() if v.name == workflow_file), None)
    if not wf_id:
        return {"error": "Không tìm thấy workflow ID trong file .ts", "status_code": 400}

    logs = []
    deploy_ok = False
    error_msg = ""
    was_active = False

    try:
        resp_before = await n8n_request("GET", f"/workflows/{wf_id}")
        if resp_before.status_code == 200:
            was_active = resp_before.json().get("active", False)
            logs.append(f"Trạng thái trước push: {'Active' if was_active else 'Inactive'}")
    except Exception:
        pass

    def _has_conflict(out: str, err: str) -> bool:
        combined = (out + err).lower()
        return "conflict detected" in combined or "conflict" in combined

    try:
        logs.append(f"▶ Pushing {workflow_file}...")
        push_cmd = ["npx", "--yes", "n8nac", "push", f"workflows/local-n8n/{workflow_file}", "--verify"]
        rc, out, err = await run_cmd(push_cmd, cwd=workspace)
        logs.append(f"stdout: {out.strip()}")
        if err.strip():
            logs.append(f"stderr: {err.strip()}")

        if rc == 0 and not _has_conflict(out, err):
            deploy_ok = True
            logs.append("✅ Push thành công!")
        elif _has_conflict(out, err) and auto_resolve_conflict:
            logs.append("⚠️ Phát hiện conflict. Đang resolve với keep-current...")
            resolve_cmd = ["npx", "--yes", "n8nac", "resolve", wf_id, "--mode", "keep-current"]
            rc2, out2, err2 = await run_cmd(resolve_cmd, cwd=workspace)
            logs.append(f"resolve: {out2.strip()}")
            if err2.strip():
                logs.append(f"resolve stderr: {err2.strip()}")

            if rc2 == 0:
                logs.append("▶ Push lại sau resolve...")
                rc3, out3, err3 = await run_cmd(push_cmd, cwd=workspace)
                logs.append(f"re-push: {out3.strip()}")
                if err3.strip():
                    logs.append(f"re-push stderr: {err3.strip()}")
                if rc3 == 0 and not _has_conflict(out3, err3):
                    deploy_ok = True
                    logs.append("✅ Push thành công sau resolve!")
                else:
                    error_msg = (out3 + err3).strip()
                    logs.append(f"❌ Re-push thất bại: {error_msg[:200]}")
            else:
                error_msg = f"Resolve thất bại: {out2} {err2}"
                logs.append(f"❌ {error_msg[:200]}")
        else:
            error_msg = (out + err).strip()
            logs.append(f"❌ Push thất bại (rc={rc}): {error_msg[:200]}")

    except Exception as e:
        error_msg = str(e)
        logs.append(f"❌ Exception: {e}")

    now_ts = datetime.now(timezone.utc)
    log_entry = json.dumps({
        "workflow_id": wf_id,
        "filename": workflow_file,
        "success": deploy_ok,
        "error": error_msg,
        "logs": logs,
        "deployed_at": now_ts.isoformat(),
    }, ensure_ascii=False)
    # pyrefly: ignore [not-async]
    await r.rpush("n8n:deploy:log", log_entry)
    # pyrefly: ignore [not-async]
    await r.ltrim("n8n:deploy:log", -50, -1)

    if deploy_ok:
        await r.set(f"n8n:deploy:last:{wf_id}", str(now_ts.timestamp()))
        if was_active:
            try:
                resp_after = await n8n_request("GET", f"/workflows/{wf_id}")
                if resp_after.status_code == 200:
                    is_still_active = resp_after.json().get("active", False)
                    if not is_still_active:
                        logs.append("🔄 Đang bật lại workflow...")
                        await n8n_request("POST", f"/workflows/{wf_id}/activate")
                        logs.append("✅ Đã bật lại workflow (Active)!")
            except Exception as e:
                logs.append(f"⚠️ Lỗi kiểm tra bật lại workflow: {e}")

    return {
        "ok": deploy_ok,
        "workflow_id": wf_id,
        "filename": workflow_file,
        "logs": logs,
        "error": error_msg,
        "deployed_at": now_ts.isoformat(),
    }


async def get_n8n_deploy_log_history() -> dict:
    """Lấy danh sách lịch sử các lần deploy gần nhất."""
    r = get_redis_client()
    try:
        # pyrefly: ignore [not-async]
        raw_logs = await r.lrange("n8n:deploy:log", -30, -1)
        entries = [json.loads(l) for l in raw_logs]
        entries.reverse()
        return {"logs": entries, "total": len(entries)}
    except Exception as e:
        return {"error": str(e), "logs": []}


async def handle_file_watch_ws(websocket: WebSocket):
    """Quản lý kết nối WebSocket cho real-time File Watching."""
    await websocket.accept()
    _ws_clients.append(websocket)
    file_mtimes: dict = {}
    wf_map = discover_workflow_files()
    for wf_id, ts_path in wf_map.items():
        try:
            file_mtimes[wf_id] = ts_path.stat().st_mtime
        except Exception:
            pass

    try:
        await websocket.send_json({"type": "connected", "message": "File watcher ready", "files": len(wf_map)})
        while True:
            await asyncio.sleep(3)
            wf_map = discover_workflow_files()
            changed = []
            for wf_id, ts_path in wf_map.items():
                try:
                    mtime = ts_path.stat().st_mtime
                    if mtime != file_mtimes.get(wf_id, 0):
                        file_mtimes[wf_id] = mtime
                        changed.append({
                            "workflow_id": wf_id,
                            "filename": ts_path.name,
                            "modified_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                        })
                except Exception:
                    pass

            if changed:
                await websocket.send_json({"type": "file_changed", "changed": changed})
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        if websocket in _ws_clients:
            _ws_clients.remove(websocket)
