"""
domains.customers.service — Business logic cho Profile khách hàng, Chat History, Leads và Export.
"""

import csv
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from domains.common.db import get_redis_client

logger = logging.getLogger(__name__)


async def get_customers_list(brand: str = "all", page: int = 1, page_size: int = 20) -> dict:
    """Lấy danh sách phân trang khách hàng từ Redis."""
    r = get_redis_client()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        all_customers = []

        for b in brands:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            keys = []
            while True:
                cursor, batch = await r.scan(cursor, match=pattern, count=200)
                keys.extend(batch)
                if cursor == 0:
                    break

            for key in keys:
                raw = await r.get(key)
                if not raw:
                    continue
                try:
                    profile = json.loads(raw)
                except Exception:
                    continue
                sender_id = key.split(":")[-1]
                all_customers.append({
                    "sender_id": sender_id,
                    "brand": b.upper(),
                    "fb_name": profile.get("fb_name", ""),
                    "phone": profile.get("phone", "") or profile.get("customer_phone", ""),
                    "area": profile.get("area", "") or profile.get("customer_location", ""),
                    "lead_stage": profile.get("lead_stage", "new"),
                    "last_intent": profile.get("last_intent", ""),
                    "last_need": profile.get("last_need", ""),
                    "last_seen_at": profile.get("last_seen_at", ""),
                    "first_seen_at": profile.get("first_seen_at", ""),
                })

        all_customers.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)
        total = len(all_customers)
        start = (page - 1) * page_size
        end = start + page_size

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "customers": all_customers[start:end],
        }
    finally:
        await r.aclose()


async def get_customer_session_detail(brand: str, sender_id: str) -> dict:
    """Xem session chat của 1 khách hàng."""
    r = get_redis_client()
    b = brand.lower()
    try:
        profile_raw = await r.get(f"{b}:customer:messenger:{sender_id}")
        session_raw = await r.get(f"{b}:session:messenger:{sender_id}")

        profile = json.loads(profile_raw) if profile_raw else {}
        session = json.loads(session_raw) if session_raw else {}

        return {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "profile": profile,
            "session": session,
        }
    finally:
        await r.aclose()


async def update_customer_profile(brand: str, sender_id: str, updates: dict) -> dict:
    """Cập nhật thông tin profile khách hàng vào Redis."""
    r = get_redis_client()
    b = brand.lower()
    customer_key = f"{b}:customer:messenger:{sender_id}"
    session_key = f"{b}:session:messenger:{sender_id}"
    try:
        raw_cust = await r.get(customer_key)
        profile = json.loads(raw_cust) if raw_cust else {}

        for k, v in updates.items():
            if v is not None:
                profile[k] = v
                if k == "phone":
                    profile["customer_phone"] = v
                elif k == "area":
                    profile["customer_location"] = v

        profile["updated_at"] = datetime.now(timezone.utc).isoformat()
        await r.set(customer_key, json.dumps(profile, ensure_ascii=False))

        # Cập nhật session tương ứng nếu có
        raw_sess = await r.get(session_key)
        if raw_sess:
            sess = json.loads(raw_sess)
            if updates.get("phone") is not None:
                sess["customer_phone"] = updates["phone"]
            if updates.get("area") is not None:
                sess["customer_location"] = updates["area"]
            if updates.get("lead_stage") is not None:
                sess["lead_stage"] = updates["lead_stage"]
            await r.set(session_key, json.dumps(sess, ensure_ascii=False))

        # Gửi thông báo Telegram nếu có SĐT mới
        phone_val = profile.get("phone", "") or profile.get("customer_phone", "")
        if phone_val and len(re.findall(r"\d", phone_val)) >= 9:
            try:
                from telegram_notifier import notify_new_lead
                await notify_new_lead(
                    brand=brand,
                    phone=phone_val,
                    area=profile.get("area", "") or profile.get("customer_location", ""),
                    fb_name=profile.get("fb_name", ""),
                    need=profile.get("last_intent", "") or profile.get("last_need", ""),
                    sender_id=sender_id,
                )
            except Exception:
                pass

        return {"success": True, "message": "Đã cập nhật thông tin khách hàng thành công!", "profile": profile}
    finally:
        await r.aclose()


async def delete_customer_data(brand: str, sender_id: str) -> dict:
    """Xóa hoàn toàn hồ sơ và session của khách hàng."""
    r = get_redis_client()
    b = brand.lower()
    try:
        await r.delete(f"{b}:customer:messenger:{sender_id}")
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã xóa hoàn toàn khách hàng {sender_id} khỏi Redis"}
    finally:
        await r.aclose()


async def reset_customer_chat_session(brand: str, sender_id: str) -> dict:
    """Reset session chat của khách."""
    r = get_redis_client()
    b = brand.lower()
    try:
        await r.delete(f"{b}:session:messenger:{sender_id}")
        return {"success": True, "message": f"Đã reset session của khách {sender_id}"}
    finally:
        await r.aclose()


async def get_customer_chat_history(brand: str, sender_id: str) -> dict:
    """Tra cứu lịch sử trò chuyện đầy đủ của khách."""
    r = get_redis_client()
    b = brand.lower()
    try:
        history_keys = [
            f"{b}:history:messenger:{sender_id}",
            f"{b}:chat:history:{sender_id}",
            f"{b}:session:history:{sender_id}",
        ]
        messages = []
        for hkey in history_keys:
            key_type = await r.type(hkey)
            if key_type == "list":
                # pyrefly: ignore [not-async]
                raw_msgs = await r.lrange(hkey, 0, 100)
                for raw in raw_msgs:
                    try:
                        messages.append(json.loads(raw))
                    except Exception:
                        messages.append({"raw": str(raw)})
                break
            elif key_type == "string":
                raw = await r.get(hkey)
                if raw:
                    try:
                        parsed = json.loads(raw)
                        messages = parsed if isinstance(parsed, list) else [parsed]
                    except Exception:
                        pass
                break

        if not messages:
            session_raw = await r.get(f"{b}:session:messenger:{sender_id}")
            if session_raw:
                sess = json.loads(session_raw)
                history_field = sess.get("conversation_history") or sess.get("messages") or []
                if isinstance(history_field, list):
                    messages = history_field
                elif isinstance(history_field, str):
                    try:
                        messages = json.loads(history_field)
                    except Exception:
                        pass

        return {
            "sender_id": sender_id,
            "brand": brand.upper(),
            "total_messages": len(messages),
            "messages": messages,
        }
    finally:
        await r.aclose()


async def export_customers_to_csv_data(brand: str = "all", has_phone: Optional[bool] = None, lead_stage: Optional[str] = None) -> str:
    """Xuất danh sách khách hàng ra chuỗi CSV."""
    r = get_redis_client()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        all_customers = []
        for b in brands:
            pattern = f"{b}:customer:messenger:*"
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=200)
                for key in keys:
                    raw = await r.get(key)
                    if not raw:
                        continue
                    try:
                        profile = json.loads(raw)
                    except Exception:
                        continue
                    sender_id = key.split(":")[-1]
                    phone_val = profile.get("phone", "") or profile.get("customer_phone", "")
                    stage = profile.get("lead_stage", "new")

                    if has_phone is True and not phone_val:
                        continue
                    if has_phone is False and phone_val:
                        continue
                    if lead_stage and stage != lead_stage:
                        continue

                    all_customers.append({
                        "brand": b.upper(),
                        "sender_id": sender_id,
                        "fb_name": profile.get("fb_name", ""),
                        "phone": phone_val,
                        "area": profile.get("area", "") or profile.get("customer_location", ""),
                        "lead_stage": stage,
                        "last_intent": profile.get("last_intent", ""),
                        "admin_notes": profile.get("admin_notes", ""),
                        "admin_tags": ", ".join(profile.get("admin_tags", [])),
                        "first_seen_at": profile.get("first_seen_at", ""),
                        "last_seen_at": profile.get("last_seen_at", ""),
                    })
                if cursor == 0:
                    break

        all_customers.sort(key=lambda x: x.get("last_seen_at", ""), reverse=True)

        output = io.StringIO()
        fieldnames = ["brand", "sender_id", "fb_name", "phone", "area",
                      "lead_stage", "last_intent", "admin_notes", "admin_tags",
                      "first_seen_at", "last_seen_at"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_customers)
        return output.getvalue()
    finally:
        await r.aclose()
