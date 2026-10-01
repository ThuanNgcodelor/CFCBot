"""
ai_agent_tools.py — Tool Calling & Function Calling Hub for CFC AI Assistant
Cung cấp các công cụ kết nối n8n, CRM Khách hàng, Shopee, Learning Queue, và RAG FAQ.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
# pyrefly: ignore [missing-import]
import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 1. TOOL SCHEMAS (JSON Schema cho Groq / OpenAI / Gemini)
# ─────────────────────────────────────────────────────────────

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_n8n_workflows",
            "description": "Lấy danh sách tất cả các workflow tự động hoá trên n8n, bao gồm ID, tên workflow, trạng thái hoạt động (active: true/false), ngày cập nhật và tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": "Nếu true, chỉ trả về các workflow đang được bật (active)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "toggle_n8n_workflow",
            "description": "Bật (activate) hoặc tắt (deactivate) một workflow trên n8n dựa trên tên hoặc ID của workflow.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_name_or_id": {
                        "type": "string",
                        "description": "Tên workflow (vd: 'Zalo Auto Reply', 'Shopee Sync', 'Chăm sóc Lead') hoặc ID của workflow trên n8n."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["activate", "deactivate", "toggle"],
                        "description": "'activate' để bật, 'deactivate' để tắt, 'toggle' để đảo trạng thái hiện tại."
                    }
                },
                "required": ["workflow_name_or_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_n8n_executions",
            "description": "Lấy lịch sử các lần thực thi gần đây của các workflow n8n để kiểm tra workflow nào chạy thành công hoặc bị lỗi (status=error).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["all", "error", "success", "waiting"],
                        "description": "Trạng thái thực thi cần lọc: 'all' (tất cả), 'error' (chỉ lỗi), 'success' (thành công)."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Số lượng bản ghi tối đa (mặc định 10, tối đa 30)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_business_stats",
            "description": "Lấy báo cáo tổng hợp tình hình kinh doanh, số lượng khách hàng mới, leads có SĐT, phân loại stage khách hàng và số câu hỏi CSKH hôm nay của ZeO và CFC Cò Bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {
                        "type": "string",
                        "enum": ["all", "zeo", "cfc"],
                        "description": "Thương hiệu cần lấy thống kê: 'all', 'zeo', hoặc 'cfc'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_shopee_catalog_summary",
            "description": "Tra cứu danh mục sản phẩm Shopee Mall của ZeO và CFC, bao gồm tên sản phẩm, giá bán, giảm giá, quy cách, từ khoá và link Shopee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_keyword": {
                        "type": "string",
                        "description": "Từ khóa tìm kiếm sản phẩm cụ thể (vd: 'viên sủi', 'ngũ cốc', 'hạt dinh dưỡng', 'canxi'). Nếu để trống sẽ trả về tổng quan danh mục."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_learning_queue_summary",
            "description": "Lấy danh sách các câu hỏi của khách hàng mà Chatbot chưa tự tin trả lời (Confidence < 55%), đang nằm trong Learning Queue chờ Admin duyệt thêm vào FAQ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Số lượng câu hỏi cần lấy (mặc định 5)."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_faq_knowledge",
            "description": "Tra cứu kịch bản câu hỏi thường gặp (FAQ) trong cơ sở dữ liệu tri thức của ZeO Vietnam hoặc CFC Cò Bay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Nội dung câu hỏi cần tra cứu kiến thức."
                    },
                    "brand": {
                        "type": "string",
                        "enum": ["zeo", "cfc"],
                        "description": "Thương hiệu cần tra cứu: 'zeo' hoặc 'cfc'."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_status",
            "description": "Kiểm tra tình trạng kỹ thuật và tài nguyên hệ thống: dung lượng RAM bộ nhớ Redis đang dùng, số lượng keys, vector index, trạng thái Ollama Embedding, n8n server, token usage và thông tin cấu hình.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component": {
                        "type": "string",
                        "enum": ["all", "redis", "ollama", "n8n"],
                        "description": "Thành phần kỹ thuật cần kiểm tra: 'all' (tất cả), 'redis' (dung lượng RAM/keys), 'ollama', hoặc 'n8n'."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_system_command",
            "description": "Thực thi câu lệnh Bash / Shell / Python CLI trên máy chủ macOS/Linux (vd: 'redis-cli info memory', 'df -h', 'ps aux | grep uvicorn', 'curl -s wttr.in/CanTho?format=3', 'cat /path/to/file', 'grep -i error logs/app.log', 'python3 -c \"...\"'). Dùng công cụ này để kiểm tra bất kỳ thông số hệ thống, đọc file, gọi API, tính toán hoặc xử lý tác vụ kỹ thuật nào.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Câu lệnh bash/shell chính xác cần chạy."
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Thư mục chạy lệnh (mặc định thư mục gốc dự án)."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_n8n_webhook",
            "description": "Bắn dữ liệu webhook sang n8n để kích hoạt các workflow tích hợp bên ngoài (vd: đọc/gửi email qua Gmail, lấy lịch từ Google Calendar, bắn thông báo Telegram/Zalo, đồng bộ Google Sheets).",
            "parameters": {
                "type": "object",
                "properties": {
                    "webhook_path": {
                        "type": "string",
                        "description": "Đường dẫn webhook trên n8n (vd: 'google-calendar', 'send-email', 'telegram-bot') hoặc URL webhook n8n."
                    },
                    "payload": {
                        "type": "object",
                        "description": "Dữ liệu JSON truyền sang cho workflow n8n xử lý."
                    }
                },
                "required": ["webhook_path"]
            }
        }
    }
]


# ─────────────────────────────────────────────────────────────
# 2. TOOL EXECUTORS (Thực thi các hàm nghiệp vụ)
# ─────────────────────────────────────────────────────────────

def _load_settings() -> dict:
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


# pyrefly: ignore [bad-function-definition]
async def _n8n_request(method: str, path: str, body: dict = None) -> Optional[httpx.Response]:
    cfg = _load_settings().get("n8n", {})
    url = cfg.get("url", "https://n8n.dinhduongcantho.io.vn")
    api_key = cfg.get("api_key", "")
    headers = {
        "Content-Type": "application/json",
        "X-N8N-API-KEY": api_key,
    }
    full_url = f"{url.rstrip('/')}/api/v1{path}"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            if method == "GET":
                return await client.get(full_url, headers=headers)
            elif method == "POST":
                return await client.post(full_url, headers=headers, json=body or {})
            elif method == "PATCH":
                return await client.patch(full_url, headers=headers, json=body or {})
    except Exception as e:
        logger.warning(f"n8n request error ({method} {path}): {e}")
        return None


async def execute_list_n8n_workflows(active_only: bool = False) -> Dict[str, Any]:
    """Lấy danh sách workflow n8n."""
    resp = await _n8n_request("GET", "/workflows?limit=100")
    if not resp or resp.status_code != 200:
        err = resp.text if resp else "Không thể kết nối đến n8n API"
        return {"error": f"Lỗi gọi n8n: {err}", "workflows": []}
    
    data = resp.json().get("data", [])
    workflows = []
    for w in data:
        is_active = w.get("active", False)
        if active_only and not is_active:
            continue
        workflows.append({
            "id": w["id"],
            "name": w["name"],
            "active": is_active,
            "updatedAt": w.get("updatedAt", "")[:19].replace("T", " "),
            "tags": [t.get("name", "") for t in w.get("tags", [])],
        })
    
    return {
        "total": len(workflows),
        "active_count": sum(1 for w in workflows if w["active"]),
        "workflows": workflows,
    }


async def execute_toggle_n8n_workflow(workflow_name_or_id: str, action: str = "toggle") -> Dict[str, Any]:
    """Bật/Tắt workflow n8n theo tên hoặc ID."""
    # 1. Lấy danh sách workflow để tìm target
    list_res = await execute_list_n8n_workflows()
    workflows = list_res.get("workflows", [])
    
    target_wf = None
    target_id = workflow_name_or_id.strip()
    
    # Tìm theo exact ID
    for w in workflows:
        if w["id"] == target_id:
            target_wf = w
            break
            
    # Tìm theo tên (case-insensitive substring)
    if not target_wf:
        query_lower = target_id.lower()
        for w in workflows:
            if query_lower in w["name"].lower():
                target_wf = w
                break
                
    if not target_wf:
        return {
            "success": False,
            "message": f"Không tìm thấy workflow nào khớp với '{workflow_name_or_id}'. Vui lòng kiểm tra lại tên workflow.",
            "available_workflows": [w["name"] for w in workflows[:10]]
        }
        
    wf_id = target_wf["id"]
    wf_name = target_wf["name"]
    is_active = target_wf["active"]
    
    # Quyết định hành động
    if action == "activate":
        should_activate = True
    elif action == "deactivate":
        should_activate = False
    else:  # toggle
        should_activate = not is_active
        
    endpoint = f"/workflows/{wf_id}/activate" if should_activate else f"/workflows/{wf_id}/deactivate"
    resp = await _n8n_request("POST", endpoint)
    
    if resp and resp.status_code == 200:
        action_verb = "BẬT (Activated)" if should_activate else "TẮT (Deactivated)"
        return {
            "success": True,
            "workflow_id": wf_id,
            "workflow_name": wf_name,
            "previous_state": is_active,
            "new_state": should_activate,
            "message": f"Đã {action_verb} thành công workflow '{wf_name}' (ID: {wf_id})."
        }
    else:
        err = resp.text if resp else "Không nhận được phản hồi từ n8n"
        return {
            "success": False,
            "workflow_id": wf_id,
            "workflow_name": wf_name,
            "message": f"Không thể thay đổi trạng thái workflow '{wf_name}': {err}"
        }


async def execute_get_n8n_executions(status: str = "all", limit: int = 10) -> Dict[str, Any]:
    """Lấy danh sách các lần thực thi gần nhất."""
    limit = min(max(1, limit), 30)
    query_param = f"?limit={limit}"
    if status and status != "all":
        query_param += f"&status={status}"
    else:
        query_param += "&status=all"
        
    resp = await _n8n_request("GET", f"/executions{query_param}")
    if not resp or resp.status_code != 200:
        return {"error": "Không thể lấy lịch sử execution từ n8n", "executions": []}
        
    data = resp.json().get("data", [])
    executions = []
    error_count = 0
    for e in data:
        st = e.get("status", "unknown")
        if st == "error":
            error_count += 1
        executions.append({
            "id": e.get("id"),
            "workflowId": e.get("workflowId"),
            "workflowName": e.get("workflowData", {}).get("name", "Unknown Workflow"),
            "status": st,
            "mode": e.get("mode", "webhook"),
            "startedAt": (e.get("startedAt") or "")[:19].replace("T", " "),
            "stoppedAt": (e.get("stoppedAt") or "")[:19].replace("T", " "),
        })
        
    return {
        "total": len(executions),
        "error_count": error_count,
        "executions": executions,
    }


async def execute_get_business_stats(brand: str = "all") -> Dict[str, Any]:
    """Lấy báo cáo số liệu kinh doanh từ Redis & Analytics."""
    try:
        from admin_routes import _get_redis
        r = _get_redis()

        brands_to_check = ["zeo", "cfc"] if brand == "all" else [brand]
        result = {}
        total_customers = 0
        total_leads = 0
        total_lq = 0

        for b in brands_to_check:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            cust_count = len(keys)
            lead_count = 0
            stages_map = {}

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue

                if profile.get("phone"):
                    lead_count += 1
                st = profile.get("lead_stage", "new")
                stages_map[st] = stages_map.get(st, 0) + 1

            # pyrefly: ignore [not-async]
            lq_len = await r.llen(f"{b}:learning_queue")

            result[b] = {
                "customers_count": cust_count,
                "leads_with_phone": lead_count,
                "learning_queue_count": lq_len,
                "lead_stages": stages_map,
            }
            total_customers += cust_count
            total_leads += lead_count
            total_lq += lq_len

        await r.aclose()

        return {
            "brand": brand,
            "total_customers": total_customers,
            "total_leads_with_phone": total_leads,
            "total_learning_queue_pending": total_lq,
            "details": result,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        logger.warning(f"get_business_stats error: {e}")
        return {"error": str(e), "message": "Không thể kết nối tới Redis để lấy số liệu."}


async def execute_get_shopee_catalog_summary(search_keyword: Optional[str] = None) -> Dict[str, Any]:
    """Tra cứu danh mục sản phẩm Shopee Mall từ Redis zeo:shopee:catalog:active."""
    try:
        from shopee_matcher import load_shopee_catalog, _fold
        from admin_routes import _get_redis
        
        products = []
        try:
            r = _get_redis()
            cached = await r.get("zeo:shopee:catalog:active")
            await r.aclose()
            if cached:
                products = json.loads(cached)
        except Exception:
            products = []
            
        if not products:
            products = load_shopee_catalog("zeo")

        if search_keyword and search_keyword.strip():
            kw_folded = _fold(search_keyword.strip())
            words = [w for w in kw_folded.split() if len(w) > 1]
            filtered = []
            for p in products:
                combined_text = _fold(f"{p.get('name', '')} {p.get('brand', '')} {' '.join(p.get('keywords', []))}")
                if kw_folded in combined_text or (words and all(w in combined_text for w in words)):
                    filtered.append(p)

            return {
                "search_keyword": search_keyword,
                "total_matched": len(filtered),
                "products": filtered[:8] if filtered else products[:4],
            }

        return {
            "total_products": len(products),
            "sample_products": [
                {
                    "name": p.get("name"),
                    "price": p.get("price"),
                    "promotion": p.get("promotion", ""),
                    "variant": p.get("variant", ""),
                    "link": p.get("shopee_url", "")
                }
                for p in products[:8]
            ]
        }
    except Exception as e:
        return {"error": str(e), "products": []}


async def execute_get_learning_queue_summary(limit: int = 5) -> Dict[str, Any]:
    """Lấy danh sách các câu hỏi trong Learning Queue."""
    try:
        from admin_routes import _get_redis
        r = _get_redis()
        
        lq_items = []
        for brand in ["zeo", "cfc"]:
            # pyrefly: ignore [not-async]
            raw_items = await r.lrange(f"{brand}:learning_queue", 0, limit - 1)
            for item_str in raw_items:
                try:
                    item = json.loads(item_str)
                    item["brand"] = brand
                    lq_items.append(item)
                except Exception:
                    pass
        await r.aclose()
        
        return {
            "total_retrieved": len(lq_items),
            "items": lq_items[:limit]
        }
    except Exception as e:
        return {"error": str(e), "items": []}


async def execute_search_faq_knowledge(query: str, brand: str = "zeo") -> Dict[str, Any]:
    """Tra cứu FAQ RAG."""
    try:
        from rag_search import semantic_search
        res = await semantic_search(query=query, brand=brand, top_k=3)
        return {
            "query": query,
            "brand": brand,
            "confidence": res.get("confidence", "low"),
            "top_intent": res.get("intent", ""),
            "answer": res.get("answer", ""),
            "score": res.get("score", 0),
        }
    except Exception as e:
        return {"error": str(e), "answer": "Không thể tra cứu cơ sở tri thức lúc này."}


async def execute_get_system_status(component: str = "all") -> Dict[str, Any]:
    """Kiểm tra tình trạng kỹ thuật của Redis, RAM, Ollama, n8n và tokens."""
    res = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    # 1. Redis Info
    if component in ("all", "redis"):
        try:
            from admin_routes import _get_redis
            r = _get_redis()
            info_mem = await r.info("memory")
            info_srv = await r.info("server")
            dbsize = await r.dbsize()
            try:
                indexes = await r.execute_command("FT._LIST")
                # pyrefly: ignore [not-iterable]
                indexes = [i.decode() if isinstance(i, bytes) else str(i) for i in indexes]
            except Exception:
                indexes = []
            # pyrefly: ignore [bad-assignment]
            res["redis"] = {
                "status": "online",
                "used_memory_ram": info_mem.get("used_memory_human", "?"),
                "peak_memory": info_mem.get("used_memory_peak_human", "?"),
                "total_keys": dbsize,
                "vector_indexes": indexes,
                "version": info_srv.get("redis_version", "?"),
                "uptime_hours": round(info_srv.get("uptime_in_seconds", 0) / 3600, 1),
            }
            await r.aclose()
        except Exception as e:
            # pyrefly: ignore [bad-assignment]
            res["redis"] = {"status": "error", "message": str(e)}

    # 2. Ollama Info
    if component in ("all", "ollama"):
        try:
            cfg = _load_settings().get("ollama", {})
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{cfg.get('base_url', 'http://127.0.0.1:11434')}/api/tags")
                models = [m["name"] for m in resp.json().get("models", [])]
                # pyrefly: ignore [bad-assignment]
                res["ollama"] = {
                    "status": "online",
                    "embed_model": cfg.get("embed_model", "bge-m3"),
                    "available_models": models,
                }
        except Exception as e:
            # pyrefly: ignore [bad-assignment]
            res["ollama"] = {"status": "offline_or_error", "message": str(e)}

    # 3. n8n Info
    if component in ("all", "n8n"):
        n8n_list = await execute_list_n8n_workflows()
        # pyrefly: ignore [bad-assignment]
        res["n8n"] = {
            "status": "online" if "error" not in n8n_list else "error",
            "total_workflows": n8n_list.get("total", 0),
            "active_workflows": n8n_list.get("active_count", 0),
        }

    # 4. Token & Engine Info
    # pyrefly: ignore [bad-assignment]
    res["ai_engine"] = {
        "active_provider": "Groq Cloud API",
        "model": "llama-3.3-70b-versatile",
        "quota_limit": "Gói Miễn Phí (Free Cloud Tier: 6,000 Requests/phút, 500,000 Tokens/phút)",
        "estimated_usage_per_turn": "Ước tính khoảng 300 - 600 tokens/lượt (bao gồm system prompt & lịch sử)",
        "cost": "Hoàn toàn miễn phí 0đ",
        "latency": "Cực nhanh (~500 tokens/giây)"
    }

    return res


async def execute_system_command(command: str, cwd: Optional[str] = None) -> Dict[str, Any]:
    """Thực thi câu lệnh Shell / CLI trên máy chủ macOS an toàn và linh hoạt."""
    import asyncio
    import os

    # Bộ lọc an toàn: Chặn các lệnh huỷ diệt dữ liệu hệ thống
    forbidden = ["rm -rf /", "rm -rf *", "mkfs", "dd if=/dev", ":(){ :|:& };:", "shutdown", "reboot"]
    for f in forbidden:
        if f in command:
            return {"success": False, "error": f"Lệnh bị chặn vì lý do an toàn bảo mật: '{command}'"}

    work_dir = cwd or str(Path(__file__).resolve().parents[2])
    if not os.path.exists(work_dir):
        work_dir = str(Path(__file__).resolve().parent)

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=15.0)
            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            return {
                "success": proc.returncode == 0,
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout[:4000],  # Cắt tối đa 4000 ký tự để không tràn context
                "stderr": stderr[:1000] if stderr else None
            }
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return {"success": False, "command": command, "error": "Câu lệnh quá thời gian chờ (Timeout 15s)."}
    except Exception as e:
        return {"success": False, "command": command, "error": str(e)}


async def execute_trigger_n8n_webhook(webhook_path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Bắn dữ liệu webhook sang n8n để kích hoạt bất kỳ workflow tích hợp nào."""
    cfg = _load_settings().get("n8n", {})
    base_url = cfg.get("url", "https://n8n.dinhduongcantho.io.vn").rstrip("/")

    if webhook_path.startswith("http://") or webhook_path.startswith("https://"):
        target_url = webhook_path
    else:
        path = webhook_path.lstrip("/")
        if not path.startswith("webhook/"):
            path = f"webhook/{path}"
        target_url = f"{base_url}/{path}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(target_url, json=payload or {})
            if resp.status_code in (200, 201):
                try:
                    res_json = resp.json()
                except Exception:
                    res_json = {"message": resp.text}
                return {
                    "success": True,
                    "webhook_url": target_url,
                    "status_code": resp.status_code,
                    "response": res_json
                }
            else:
                return {
                    "success": False,
                    "webhook_url": target_url,
                    "status_code": resp.status_code,
                    "error": resp.text[:500]
                }
    except Exception as e:
        return {"success": False, "webhook_url": target_url, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# 3. TOOL DISPATCHER (Điều phối gọi hàm từ tên tool của AI)
# ─────────────────────────────────────────────────────────────

async def dispatch_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Thực thi tool tương ứng và trả về dictionary kết quả."""
    logger.info(f"[AI Agent Tool] Calling '{tool_name}' with args: {arguments}")
    
    try:
        if tool_name == "list_n8n_workflows":
            return await execute_list_n8n_workflows(
                active_only=arguments.get("active_only", False)
            )
        elif tool_name == "toggle_n8n_workflow":
            return await execute_toggle_n8n_workflow(
                workflow_name_or_id=arguments.get("workflow_name_or_id", ""),
                action=arguments.get("action", "toggle")
            )
        elif tool_name == "get_n8n_executions":
            return await execute_get_n8n_executions(
                status=arguments.get("status", "all"),
                limit=arguments.get("limit", 10)
            )
        elif tool_name == "get_business_stats":
            return await execute_get_business_stats(
                brand=arguments.get("brand", "all")
            )
        elif tool_name == "get_shopee_catalog_summary":
            return await execute_get_shopee_catalog_summary(
                search_keyword=arguments.get("search_keyword")
            )
        elif tool_name == "get_learning_queue_summary":
            return await execute_get_learning_queue_summary(
                limit=arguments.get("limit", 5)
            )
        elif tool_name == "search_faq_knowledge":
            return await execute_search_faq_knowledge(
                query=arguments.get("query", ""),
                brand=arguments.get("brand", "zeo")
            )
        elif tool_name == "get_system_status":
            return await execute_get_system_status(
                component=arguments.get("component", "all")
            )
        elif tool_name == "execute_system_command":
            return await execute_system_command(
                command=arguments.get("command", ""),
                cwd=arguments.get("cwd")
            )
        elif tool_name == "trigger_n8n_webhook":
            return await execute_trigger_n8n_webhook(
                webhook_path=arguments.get("webhook_path", ""),
                payload=arguments.get("payload")
            )
        else:
            return {"error": f"Tool '{tool_name}' không được hỗ trợ."}
    except Exception as e:
        logger.error(f"[AI Agent Tool] Error in '{tool_name}': {e}", exc_info=True)
        return {"error": str(e), "tool": tool_name}
