"""
domains.system.service — Business logic cho System, Health, Analytics và Settings.
"""

import json
import logging
from datetime import datetime, timezone
import httpx
from domains.common.config import get_cfg, save_settings
from domains.common.db import get_redis_client, get_n8n_config, n8n_request

logger = logging.getLogger(__name__)


async def get_system_status() -> dict:
    """Kiểm tra trạng thái toàn diện: Redis, Ollama, n8n, Python API."""
    cfg = get_cfg()
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {}
    }

    # Redis check
    try:
        r = get_redis_client()
        await r.ping()
        info = await r.info("server")
        result["services"]["redis"] = {
            "status": "ok",
            "version": info.get("redis_version", "?"),
            "uptime_seconds": info.get("uptime_in_seconds", 0),
        }
        await r.aclose()
    except Exception as e:
        result["services"]["redis"] = {"status": "error", "detail": str(e)}

    # Ollama check
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{cfg['ollama']['base_url']}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            result["services"]["ollama"] = {
                "status": "ok",
                "models": models,
                "embed_model": cfg["ollama"]["embed_model"],
                "embed_ready": any(cfg["ollama"]["embed_model"].split(":")[0] in m for m in models),
            }
    except Exception as e:
        result["services"]["ollama"] = {"status": "error", "detail": str(e)}

    # n8n check
    n8n = get_n8n_config()
    try:
        headers = {"X-N8N-API-KEY": n8n["api_key"]} if n8n.get("api_key") else {}
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{n8n['url']}/api/v1/workflows", headers=headers)
            if resp.status_code == 200:
                wf_data = resp.json()
                workflows = wf_data.get("data", [])
                active_count = sum(1 for w in workflows if w.get("active"))
                result["services"]["n8n"] = {
                    "status": "ok",
                    "url": n8n["url"],
                    "total_workflows": len(workflows),
                    "active_workflows": active_count,
                }
            else:
                result["services"]["n8n"] = {"status": "no_api_key", "url": n8n["url"]}
    except Exception as e:
        result["services"]["n8n"] = {"status": "error", "detail": str(e)}

    # Python API check
    result["services"]["python_api"] = {"status": "ok", "version": "2.1.0"}
    return result


async def get_stats_today() -> dict:
    """Thống kê tổng quan khách hàng, leads, intent và learning queue hôm nay."""
    r = get_redis_client()
    try:
        stats = {
            "zeo": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "cfc": {"customers": 0, "lead_stages": {}, "top_intents": {}},
            "total_customers": 0,
        }

        for brand in ["zeo", "cfc"]:
            pattern = f"{brand}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            stats[brand]["customers"] = len(keys)
            stats["total_customers"] += len(keys)

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                stage = profile.get("lead_stage", "new")
                stats[brand]["lead_stages"][stage] = stats[brand]["lead_stages"].get(stage, 0) + 1
                intent = profile.get("last_intent", "")
                if intent:
                    stats[brand]["top_intents"][intent] = stats[brand]["top_intents"].get(intent, 0) + 1

            # Sort top intents
            stats[brand]["top_intents"] = dict(
                sorted(stats[brand]["top_intents"].items(), key=lambda x: -x[1])[:8]
            )

        # Learning queue counts
        for brand in ["zeo", "cfc"]:
            lq_key = f"{brand}:learning:queue"
            lq_len = await r.llen(lq_key) if await r.exists(lq_key) else 0
            stats[brand]["learning_queue_count"] = lq_len

        return stats
    finally:
        await r.aclose()


async def get_weekly_analytics() -> dict:
    """Lấy dữ liệu phân tích 7 ngày gần nhất."""
    r = get_redis_client()
    try:
        today = datetime.now()
        days = []
        for i in range(6, -1, -1):
            d = datetime.fromtimestamp(today.timestamp() - i * 86400)
            date_str = d.strftime("%Y-%m-%d")
            label = d.strftime("%d/%m")
            snap_key = f"cfc:analytics:snapshot:{date_str}"
            raw = await r.get(snap_key)
            if raw:
                try:
                    data = json.loads(raw)
                except Exception:
                    data = {}
            else:
                data = {}
            days.append({
                "date": date_str,
                "label": label,
                "total_customers": data.get("total_customers", 0),
                "zeo_customers": data.get("zeo", {}).get("customers", 0),
                "cfc_customers": data.get("cfc", {}).get("customers", 0),
                "total_leads": data.get("total_leads", 0),
                "leads_ready": data.get("leads_ready", 0),
                "learning_queue": data.get("learning_queue_total", 0),
            })
        return {"days": days}
    finally:
        await r.aclose()


async def save_daily_snapshot() -> dict:
    """Lưu snapshot dữ liệu vào Redis mỗi ngày."""
    r = get_redis_client()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        snap_key = f"cfc:analytics:snapshot:{today_str}"
        st = await get_stats_today()

        total_leads = 0
        leads_ready = 0
        for brand in ["zeo", "cfc"]:
            stages = st.get(brand, {}).get("lead_stages", {})
            total_leads += sum(v for k, v in stages.items() if k != "new")
            leads_ready += stages.get("lead_ready", 0) + stages.get("qualified", 0)

        snap = {
            "date": today_str,
            "total_customers": st.get("total_customers", 0),
            "zeo": st.get("zeo", {}),
            "cfc": st.get("cfc", {}),
            "total_leads": total_leads,
            "leads_ready": leads_ready,
            "learning_queue_total": (
                st.get("zeo", {}).get("learning_queue_count", 0)
                + st.get("cfc", {}).get("learning_queue_count", 0)
            ),
            "saved_at": datetime.now().isoformat(),
        }
        await r.setex(snap_key, 60 * 60 * 24 * 8, json.dumps(snap, ensure_ascii=False))
        return {"success": True, "snapshot": snap}
    finally:
        await r.aclose()


async def test_telegram_connection(bot_token: str, chat_id: str, message: str = "") -> dict:
    """Thử nghiệm gửi tin nhắn Telegram."""
    from telegram_notifier import send_telegram_message
    msg = message or "🧪 <b>CFC AI System:</b> Kiểm tra kết nối Telegram Bot thành công!"
    success = await send_telegram_message(msg, bot_token=bot_token, chat_id=chat_id)
    return {"success": success}
