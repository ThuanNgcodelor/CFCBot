"""
domains.learning.service — Business logic cho Learning Queue, Duyệt FAQ và AI Tự Học.
"""

import json
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException
from domains.common.db import get_redis_client
from domains.common.config import get_cfg

logger = logging.getLogger(__name__)


async def fetch_learning_queue_items(brand: str = "all", limit: int = 50) -> dict:
    """Lấy danh sách các câu hỏi chưa chắc từ Learning Queue."""
    r = get_redis_client()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        items = []

        for b in brands:
            lq_key = f"{b}:learning:queue"
            lq_key_alt = f"{b}:kb:learning:queue"

            for key in [lq_key, lq_key_alt]:
                key_type = await r.type(key)
                if key_type == "none":
                    continue

                if key_type == "list":
                    # pyrefly: ignore [not-async]
                    raw_items = await r.lrange(key, 0, limit - 1)
                elif key_type == "set":
                    # pyrefly: ignore [not-async]
                    raw_items = list(await r.smembers(key))[:limit]
                else:
                    continue

                for raw in raw_items:
                    try:
                        item = json.loads(raw)
                        item["brand"] = b.upper()
                        item["queue_key"] = key
                        items.append(item)
                    except Exception:
                        items.append({"raw": raw, "brand": b.upper(), "queue_key": key})

        return {"total": len(items), "items": items}
    finally:
        await r.aclose()


async def dismiss_learning_queue_item(queue_key: str, raw_value: str) -> bool:
    """Xóa bỏ một câu hỏi khỏi Learning Queue."""
    r = get_redis_client()
    try:
        # pyrefly: ignore [not-async]
        removed = await r.lrem(queue_key, 1, raw_value)
        return removed > 0
    finally:
        await r.aclose()


async def approve_and_add_faq_item(brand: str, req_data: dict) -> dict:
    """Duyệt câu hỏi từ Learning Queue và nạp thẳng vào Redis Vector Index."""
    from knowledge_sync import ensure_index, build_embed_text
    from embedder import embed_text as get_embed, vec_to_bytes, get_embed_dim

    r_bytes = get_redis_client(decode=False)
    r_text = get_redis_client(decode=True)

    try:
        kb_key = f"{brand.lower()}:kb:basic:active"
        raw = await r_text.get(kb_key)
        if not raw:
            raise HTTPException(status_code=404, detail=f"KB key '{kb_key}' không tìm thấy")

        data = json.loads(raw)
        if isinstance(data, dict):
            items_raw = data.get("snapshot_json") or data.get("knowledgeItems") or "[]"
            items = json.loads(items_raw) if isinstance(items_raw, str) else items_raw
            wrapper = data
        else:
            items = data
            wrapper = None

        new_item = {
            "active": True,
            "brand": brand.upper(),
            "category": req_data.get("category", ""),
            "intent": req_data.get("intent", ""),
            "question_examples": req_data.get("question_examples", []),
            "answer": req_data.get("answer", ""),
            "priority": 80,
            "source_id": f"learning_approved_{int(time.time())}",
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "audience": "customer",
            "answer_mode": req_data.get("answer_mode", "direct"),
            "risk_level": req_data.get("risk_level", "low"),
        }

        items.append(new_item)
        if wrapper:
            wrapper["snapshot_json"] = json.dumps(items, ensure_ascii=False)
            await r_text.set(kb_key, json.dumps(wrapper, ensure_ascii=False))
        else:
            await r_text.set(kb_key, json.dumps(items, ensure_ascii=False))

        index_name = f"{brand.lower()}:vec:faq"
        embed_dim = get_embed_dim()
        await ensure_index(r_bytes, index_name, embed_dim)

        embed_text_str = build_embed_text(new_item)
        vec = await get_embed(embed_text_str)
        if vec:
            doc_key = f"{index_name}:doc:{new_item['source_id']}:{new_item['intent']}"
            # pyrefly: ignore [not-async]
            await r_bytes.hset(doc_key, mapping={
                "embedding": vec_to_bytes(vec),
                "intent": new_item["intent"],
                "brand": brand.upper(),
                "category": new_item["category"],
                "answer": new_item["answer"],
                "answer_mode": new_item["answer_mode"],
                "risk_level": new_item["risk_level"],
                "source_id": new_item["source_id"],
                "priority": 80,
            })

        return {"success": True, "intent": new_item["intent"], "message": "Đã thêm vào KB và cập nhật Vector Index"}
    finally:
        await r_bytes.aclose()
        await r_text.aclose()


async def suggest_answers_for_learning_queue(brand: str = "all") -> dict:
    """AI gom nhóm câu hỏi và gợi ý câu trả lời chuẩn."""
    from ai_engine import generate_ai_text
    r = get_redis_client()
    try:
        brands = ["zeo", "cfc"] if brand == "all" else [brand.lower()]
        raw_questions = []
        for b in brands:
            for lq_key in [f"{b}:learning:queue", f"{b}:kb:learning:queue"]:
                key_type = await r.type(lq_key)
                if key_type == "list":
                    # pyrefly: ignore [not-async]
                    items = await r.lrange(lq_key, 0, 50)
                elif key_type == "set":
                    # pyrefly: ignore [not-async]
                    items = list(await r.smembers(lq_key))[:50]
                else:
                    continue
                for raw in items:
                    try:
                        item = json.loads(raw)
                        q = item.get("user_message") or item.get("query") or str(raw)
                        raw_questions.append({"brand": b.upper(), "question": q, "raw": raw})
                    except Exception:
                        raw_questions.append({"brand": b.upper(), "question": str(raw), "raw": raw})
    finally:
        await r.aclose()

    if not raw_questions:
        return {"success": True, "suggestions": [], "message": "Learning Queue trống!"}

    q_list = "\n".join([f"- [{i+1}] ({q['brand']}) {q['question']}" for i, q in enumerate(raw_questions[:30])])
    prompt = f"""Bạn là chuyên gia phân tích FAQ chatbot ZeO/CFC bán hàng phân bón và nước giặt.

Dưới đây là {len(raw_questions[:30])} câu hỏi khách hàng mà chatbot CHƯA trả lời được (Learning Queue):

{q_list}

Hãy:
1. Gom nhóm các câu có ý nghĩa tương đồng lại với nhau
2. Đặt tên intent ngắn gọn cho từng nhóm (VD: "wholesale_price", "product_usage", "return_policy")
3. Viết câu trả lời chuẩn tiếng Việt cho từng nhóm (ngắn gọn, thân thiện, chuyên nghiệp)

Trả về JSON array:
[{{"intent": "tên_intent", "brand": "ZEO/CFC", "sample_questions": ["câu hỏi mẫu"], "suggested_answer": "câu trả lời gợi ý", "question_indices": [1,2,3]}}]

Chỉ trả về JSON, không giải thích thêm."""

    ai_res = await generate_ai_text(prompt=prompt, system_prompt="Bạn là chuyên gia cấu trúc FAQ.", preferred_provider="groq")
    ai_raw = ai_res.get("text", "")
    suggestions = []
    try:
        json_start = ai_raw.find("[")
        json_end = ai_raw.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            suggestions = json.loads(ai_raw[json_start:json_end])
    except Exception:
        suggestions = [{"intent": "ai_error", "suggested_answer": ai_raw, "sample_questions": [], "brand": brand.upper()}]

    return {
        "success": True,
        "total_questions": len(raw_questions),
        "suggestions": suggestions,
        "raw_questions": raw_questions[:30],
    }
