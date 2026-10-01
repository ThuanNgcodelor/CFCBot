"""
rag_search.py — Tìm kiếm ngữ nghĩa (Semantic Search) & In-Memory Hot Knowledge Cache cho ZeO & CFC.

Hỗ trợ:
  1. In-Memory Hot Knowledge Cache: Load toàn bộ FAQ vào RAM khi khởi động / sync (< 1ms lookup).
  2. Fast Lexical & Exact Matcher: Match cụm từ, bí danh, BM25-like token overlap, entity anchor mà không cần gọi Ollama.
  3. RediSearch KNN Vector Search (bge-m3): Dành riêng cho các câu mơ hồ / đa nghĩa.
  4. Degraded Mode: Khi Ollama bận / timeout, tự động fallback về top lexical candidate thay vì báo lỗi hoặc no-knowledge.
"""

import csv
import hashlib
import json
import logging
import re
import struct
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import redis.asyncio as aioredis

from embedder import embed_text, vec_to_bytes, get_embed_dim

logger = logging.getLogger(__name__)

_redis_pool: Optional[aioredis.Redis] = None

# In-Memory Hot Knowledge Store
_knowledge_items: dict[str, list[dict]] = {"zeo": [], "cfc": []}
_intent_map: dict[str, dict[str, dict]] = {"zeo": {}, "cfc": {}}
_phrase_map: dict[str, dict[str, str]] = {"zeo": {}, "cfc": {}}
_cache_loaded: dict[str, bool] = {"zeo": False, "cfc": False}
_cache_status: dict[str, dict[str, Any]] = {"zeo": {}, "cfc": {}}

VI_QUERY_ALIASES = {
    "k": "khong",
    "ko": "khong",
    "kh": "khong",
    "hok": "khong",
    "hem": "khong",
    "hong": "khong",
    "dc": "duoc",
    "dk": "duoc",
    "sp": "san pham",
    "sdt": "so dien thoai",
    "ssdt": "so dien thoai",
    "dt": "dien thoai",
    "cty": "cong ty",
    "npp": "nha phan phoi",
    "web": "website",
    "wed": "website",
    "wep": "website",
    "shoppe": "shopee",
    "sopi": "shopee",
    "tiktok": "tik tok",
    "oplis": "oplus",
    "bn": "bao nhieu",
    "nhiu": "nhieu",
    "ship": "giao hang",
}

VI_STOPWORDS = {
    "a", "ạ", "anh", "chi", "em", "toi", "minh", "ban", "shop", "ad", "admin", "ben", "nay",
    "la", "co", "khong", "duoc", "cho", "xin", "hoi", "ve", "gi", "nao", "nhe", "nha", "voi",
    "muon", "can", "xem", "thong", "tin", "tu", "van", "hien", "tai", "cua", "do", "kia",
}


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


async def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        cfg = _load_settings()["redis"]
        _redis_pool = aioredis.Redis(
            host=cfg["host"],
            port=int(cfg["port"]),
            password=cfg["password"],
            db=int(cfg.get("db", 0)),
            decode_responses=False,
        )
    return _redis_pool


def get_index_name(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_index_name"]
    return cfg["rag"]["zeo_index_name"]


def _cosine_to_confidence(distance: float) -> float:
    similarity = 1.0 - (distance / 2.0)
    return round(max(0.0, min(1.0, similarity)), 4)


def _normalize_vi_query(text: str) -> str:
    t = unicodedata.normalize("NFD", str(text or ""))
    t = re.sub(r"[\u0300-\u036f]", "", t)
    t = t.replace("đ", "d").replace("Đ", "d")
    t = re.sub(r"[^a-zA-Z0-9\s]", " ", t).lower()
    t = re.sub(r"\bcskh\b", "cham soc khach hang", t)
    t = re.sub(r"\b(cham soc|ho tro)\s+kh\b", r"\1 khach hang", t)
    tokens = [VI_QUERY_ALIASES.get(token, token) for token in t.split() if token]
    return " ".join(tokens).strip()


def _tokenize_vi(text: str) -> set[str]:
    return {token for token in _normalize_vi_query(text).split() if len(token) > 1 and token not in VI_STOPWORDS}


def _has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text))


def _is_customer_query_for_agent_content(norm_q: str) -> bool:
    return not _has(r"\b(noi dung|bai dang|kich ban|caption|video|reels|mau|viet bai|quang cao)\b", norm_q)


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(str(value or default))
    except Exception:
        return default


def _clamp_score(score: float) -> float:
    return round(max(0.0, min(1.0, score)), 4)


# ─────────────────────────────────────────────────────────────
# In-Memory Knowledge Cache Loading
# ─────────────────────────────────────────────────────────────

def _load_csv_fallback(brand: str) -> list[dict]:
    """Đọc từ file CSV local nếu Redis snapshot chưa có dữ liệu."""
    base_dir = Path(__file__).parent.parent.parent / "google_upload"
    filename = (
        "zeo_faq_google_sheet_from_ZeoN8n_2026_08_13.csv"
        if brand.lower() == "zeo"
        else "cfc_faq_google_sheet_from_CfcCoBayN8n_2026_08_13.csv"
    )
    csv_path = base_dir / filename
    if not csv_path.exists():
        logger.warning("CSV fallback not found at %s", csv_path)
        return []

    items = []
    try:
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                is_active = str(row.get("active", "")).strip().upper()
                if is_active in ("TRUE", "1", "YES", ""):
                    items.append({
                        "intent": row.get("intent", "").strip(),
                        "answer": row.get("answer", "").strip(),
                        "answer_mode": row.get("answer_mode", "direct").strip(),
                        "risk_level": row.get("risk_level", "low").strip(),
                        "category": row.get("category", "faq").strip(),
                        "source_id": row.get("source_id", "").strip(),
                        "priority": row.get("priority", "0").strip(),
                        "question_examples": row.get("question_examples", "").strip(),
                        "learning_tags": row.get("learning_tags", "").strip(),
                        "audience": row.get("audience", "customer").strip(),
                        "profile_slots": row.get("profile_slots", "").strip(),
                        "escalation_policy": row.get("escalation_policy", "").strip(),
                    })
    except Exception as e:
        logger.error("Error reading CSV fallback (%s): %s", csv_path, e)
    return items


async def refresh_knowledge_cache(
    brand: Optional[str] = None,
    *,
    strict: bool = False,
    snapshot_key: Optional[str] = None,
) -> dict[str, Any]:
    """Load customer-eligible FAQ atomically; strict sync never falls back to CSV."""
    brands = ["zeo", "cfc"] if not brand else [brand.lower()]
    if any(b not in {"zeo", "cfc"} for b in brands):
        raise ValueError("brand must be 'zeo' or 'cfc'")
    if snapshot_key and len(brands) != 1:
        raise ValueError("snapshot_key requires exactly one brand")
    r = await get_redis()
    cfg = _load_settings()
    refresh_meta: dict[str, Any] = {"status": "ok", "brands": {}}

    for b in brands:
        active_kb_key = cfg["rag"]["cfc_kb_key"] if b == "cfc" else cfg["rag"]["zeo_kb_key"]
        candidate_kb_key = active_kb_key.removesuffix(":active") + ":candidate"
        kb_key = str(snapshot_key or active_kb_key).strip()
        if kb_key not in {active_kb_key, candidate_kb_key}:
            raise ValueError("snapshot_key is outside the approved active/candidate keys")
        items: list[dict] = []
        source = "redis"
        snapshot_hash = ""

        try:
            raw_snap = await r.get(kb_key)
            if raw_snap:
                raw_str = raw_snap.decode("utf-8") if isinstance(raw_snap, bytes) else str(raw_snap)
                snapshot_hash = "sha256:" + hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
                data = json.loads(raw_str)
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    snap = data.get("snapshot_json") or data.get("knowledgeItems") or data.get("snapshot")
                    if isinstance(snap, str):
                        items = json.loads(snap)
                    elif isinstance(snap, list):
                        items = snap
        except Exception as e:
            if strict:
                raise RuntimeError(f"REDIS_SNAPSHOT_READ_FAILED:{b}") from e
            logger.warning("Could not load snapshot from Redis for %s: %s", b, e)

        if not items:
            if strict:
                raise RuntimeError(f"REDIS_SNAPSHOT_EMPTY_OR_INVALID:{b}")
            items = _load_csv_fallback(b)
            source = "csv_fallback"
            snapshot_hash = "sha256:" + hashlib.sha256(
                json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

        eligible_items: list[dict] = []
        next_intent_map: dict[str, dict] = {}
        next_phrase_map: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            active = str(item.get("active", "true")).strip().lower() in {"true", "1", "yes", ""}
            audience = str(item.get("audience", "customer")).strip().lower()
            intent = item.get("intent", "").strip()
            answer = str(item.get("answer", "")).strip()
            if not active or audience == "internal" or not intent or not answer:
                continue
            eligible_items.append(item)
            next_intent_map[intent] = item

            # Index tất cả câu hỏi mẫu và bí danh
            raw_examples = item.get("question_examples", "")
            examples = [e.strip() for e in str(raw_examples).split(";") if e.strip()] if isinstance(raw_examples, str) else list(raw_examples)
            for ex in examples:
                norm_ex = _normalize_vi_query(ex)
                if norm_ex:
                    next_phrase_map[norm_ex] = intent

        if not eligible_items:
            if strict:
                raise RuntimeError(f"NO_CUSTOMER_ELIGIBLE_ITEMS:{b}")
            logger.warning("No customer-eligible knowledge items loaded for %s", b)

        # Atomic in-process swap: a failed parse/build leaves the previous cache intact.
        _knowledge_items[b] = eligible_items
        _intent_map[b] = next_intent_map
        _phrase_map[b] = next_phrase_map
        _cache_loaded[b] = True
        _cache_status[b] = {
            "status": "ok",
            "source": source,
            "snapshot_key": kb_key,
            "snapshot_hash": snapshot_hash,
            "item_count": len(eligible_items),
            "phrase_count": len(next_phrase_map),
            "loaded_at": datetime.now(timezone.utc).isoformat(),
        }
        refresh_meta["brands"][b] = {
            "source": source,
            "snapshot_key": kb_key,
            "item_count": len(eligible_items),
            "phrase_count": len(next_phrase_map),
            "snapshot_hash": snapshot_hash,
            "loaded_at": _cache_status[b]["loaded_at"],
        }
        logger.info("In-memory knowledge cache loaded for %s: %d items, %d indexed phrases", b.upper(), len(eligible_items), len(next_phrase_map))
    return refresh_meta


def get_knowledge_runtime_status(brand: Optional[str] = None) -> dict[str, Any]:
    """Read-only in-process cache status; unknown stays explicit after a restart."""
    brands = [brand.lower()] if brand else ["zeo", "cfc"]
    return {
        "schema_version": 1,
        "brands": {
            current: {
                "loaded": bool(_cache_loaded.get(current)),
                **dict(_cache_status.get(current) or {}),
            }
            for current in brands if current in {"zeo", "cfc"}
        },
    }


async def _ensure_cache_loaded(brand: str):
    b = brand.lower()
    if not _cache_loaded.get(b):
        await refresh_knowledge_cache(b)


# ─────────────────────────────────────────────────────────────
# Fast Lexical Search (< 2ms In-Memory)
# ─────────────────────────────────────────────────────────────

def fast_lexical_search(
    query: str,
    brand: str,
    top_k: int = 5,
    exclude_fact_ids: Optional[list[str]] = None,
    category_filter: Optional[str] = None,
) -> list[dict]:
    """
    Tìm kiếm nhanh trong bộ nhớ RAM bằng Normalized Exact Match + Token Overlap / BM25-like heuristic.
    Tốc độ: < 1ms - 2ms.
    """
    b = brand.lower()
    norm_q = _normalize_vi_query(query)
    q_tokens = _tokenize_vi(query)
    exclude_set = set(exclude_fact_ids or [])

    # 1. Exact Normalized Phrase Match (Tối đa tin cậy)
    if norm_q in _phrase_map.get(b, {}):
        matched_intent = _phrase_map[b][norm_q]
        item = _intent_map[b].get(matched_intent)
        if (
            item
            and item.get("intent") not in exclude_set
            and (not category_filter or str(item.get("category") or "") == category_filter)
        ):
            return [{
                "intent": item["intent"],
                "answer": item["answer"],
                "answer_mode": item.get("answer_mode", "direct"),
                "risk_level": item.get("risk_level", "low"),
                "category": item.get("category", "faq"),
                "source_id": item.get("source_id", ""),
                "priority": item.get("priority", "0"),
                "question_examples": item.get("question_examples", ""),
                "learning_tags": item.get("learning_tags", ""),
                "audience": item.get("audience", "customer"),
                "score": 0.98,
                "retrieval_method": "exact_phrase",
            }]

    # 2. Token Overlap & Weighted Heuristic Match
    candidates = []
    for item in _knowledge_items.get(b, []):
        intent = item.get("intent", "")
        if intent in exclude_set or not intent:
            continue

        raw_examples = item.get("question_examples", "")
        examples = [e.strip() for e in str(raw_examples).split(";") if e.strip()] if isinstance(raw_examples, str) else list(raw_examples)
        answer = item.get("answer", "")
        tags = item.get("learning_tags", "")
        category = item.get("category", "")
        audience = item.get("audience", "customer")
        if category_filter and str(category) != category_filter:
            continue

        # Kiểm tra token overlap với các question examples
        best_example_overlap = 0.0
        best_phrase_match = False

        for ex in examples:
            ex_norm = _normalize_vi_query(ex)
            ex_tokens = _tokenize_vi(ex)
            if not ex_tokens:
                continue

            # Substring match
            if len(norm_q) >= 6 and (norm_q in ex_norm or ex_norm in norm_q):
                best_phrase_match = True

            overlap = q_tokens & ex_tokens
            if q_tokens:
                # Jaccard + Recall
                recall = len(overlap) / len(q_tokens)
                precision = len(overlap) / len(ex_tokens)
                score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
                if score > best_example_overlap:
                    best_example_overlap = score

        base_score = best_example_overlap
        if best_phrase_match:
            base_score = max(base_score, 0.85)

        # Entity Anchoring Rules (Tên riêng & thuộc tính đặc thù phải boost đúng intent)
        adjustment = 0.0

        # Toilet / Bồn cầu / Javen
        if _has(r"\b(toilet|bon cau)\b", norm_q):
            if "toilet" in intent:
                adjustment += 0.35
            if "detergent" in intent or "bot giat" in intent:
                adjustment -= 0.40

        if _has(r"\bjaven\b", norm_q):
            if "javen" in intent:
                adjustment += 0.35

        # Enzyme Thụy Điển
        if _has(r"\benzyme\b", norm_q) or _has(r"thuy dien", norm_q):
            if "zeo_detergent_technology" in intent or "detergent_technology" in intent:
                adjustment += 0.35

        # Nước lau sàn
        if _has(r"(lau san|nuoc lau nha|lau nha)", norm_q):
            if _has(r"(mui|huong|thom)", norm_q) and "floor_cleaner_features" in intent:
                adjustment += 0.35
            elif "floor_cleaner" in intent:
                adjustment += 0.25
            if "detergent" in intent:
                adjustment -= 0.30

        # Đổi trả quy trình vs chính sách
        if _has(r"(quy trinh|cac buoc|lam sao de doi|cach doi tra)", norm_q) and "return_process" in intent:
            adjustment += 0.30
        elif _has(r"(doi tra ap dung|kenh nao duoc doi tra|kenh doi tra)", norm_q) and "return_policy_scope" in intent:
            adjustment += 0.30

        # Shipping time and fee vs complaint
        if _has(r"(may ngay|bao lau|phi ship|cuoc|van chuyen bao lau|freeship)", norm_q) and not _has(r"(cham|tre|that lac|qua 3 ngay)", norm_q):
            if "shipping_time_and_fee" in intent:
                adjustment += 0.35
            if "complaint" in intent:
                adjustment -= 0.40

        # Return eligible cases vs excluded cases
        if _has(r"(rach|be|vo|loi|hu|hong)", norm_q) and not _has(r"(khong duoc|ngoai le|tu choi)", norm_q):
            if "return_eligible_cases" in intent:
                adjustment += 0.30

        # Return claim deadlines vs complaint response time
        if _has(r"(thoi han|bao lau de|trong vong may ngay|han doi tra|khiem nai trong)", norm_q) and not _has(r"(phan hoi|tiep nhan)", norm_q):
            if "return_claim_deadlines" in intent:
                adjustment += 0.30

        # Refund processing time vs complaint / shipping
        if _has(r"(hoan tien|nhan lai tien|tra lai tien|tien hoan tra)", norm_q):
            if "refund_processing_time" in intent:
                adjustment += 0.45
            if "complaint" in intent or "shipping" in intent:
                adjustment -= 0.45

        # ZIF
        # if _has(r"\bzif\b", norm_q):
        #     if "zif" in intent or "dishwashing" in intent:
        #         adjustment += 0.35
        #     if "catalog" in intent:
        #         adjustment -= 0.15

        # PANO
        if _has(r"\bpano\b", norm_q):
            if _has(r"(mui|huong|mau|do xanh hong cam tim)", norm_q) and "pano_laundry_fragrance_options" in intent:
                adjustment += 0.35
            elif _has(r"(veilex|khu mui)", norm_q) and "pano_veilex_odor_control" in intent:
                adjustment += 0.35
            elif "pano" in intent:
                adjustment += 0.20

        # OPLUS
        if _has(r"\boplus\b", norm_q):
            if _has(r"(ion|trang sang)", norm_q) and "oplus_detergent_ion_technology" in intent:
                adjustment += 0.35
            elif "oplus" in intent:
                adjustment += 0.20

        # NPK / Hữu cơ CFC
        if _has(r"\bnpk\b", norm_q) and "cfc_npk_product_info" in intent:
            adjustment += 0.35
        if _has(r"(huu co|sinh hoc)", norm_q) and "cfc_organic_fertilizer_info" in intent:
            adjustment += 0.35

        # Tránh audience agent
        if audience == "agent" and _is_customer_query_for_agent_content(norm_q):
            adjustment -= 0.30

        # Hạ điểm price_inquiry khi không có từ khóa hỏi giá và tăng điểm overview khi hỏi dòng sản phẩm
        if not _has(r"\b(gia|bao gia|bang gia|bao nhieu tien|nhieu tien|gia ban|gia ca|xin gia)\b", norm_q):
            if "price_inquiry" in intent:
                adjustment -= 0.35
            if _has(r"(co\b.*\b(khong|hong|ko|k)|co nhung|cac dong|san pham gi|co san pham|co bot giat|co nuoc giat|co nuoc rua chen)", norm_q) and "overview" in intent:
                adjustment += 0.25

        final_item_score = _clamp_score(base_score + adjustment)
        if final_item_score >= 0.40:
            candidates.append({
                "intent": intent,
                "answer": answer,
                "answer_mode": item.get("answer_mode", "direct"),
                "risk_level": item.get("risk_level", "low"),
                "category": category,
                "source_id": item.get("source_id", ""),
                "priority": item.get("priority", "0"),
                "question_examples": raw_examples,
                "learning_tags": tags,
                "audience": audience,
                "score": final_item_score,
                "retrieval_method": "in_memory_lexical",
            })

    candidates.sort(key=lambda x: (x["score"], _safe_int(x["priority"])), reverse=True)
    return candidates[:top_k]


# ─────────────────────────────────────────────────────────────
# Semantic Search (Hybrid Lexical + Vector + Rerank)
# ─────────────────────────────────────────────────────────────

def _rerank_results(query: str, brand: str, parsed_results: list[dict]) -> list[dict]:
    """Rerank top-k bằng lexical/entity hints để vector gần nghĩa không bắt nhầm intent."""
    norm_q = _normalize_vi_query(query)
    q_tokens = _tokenize_vi(query)

    for idx, item in enumerate(parsed_results):
        combined = " ".join(str(item.get(field, "")) for field in [
            "intent", "category", "question_examples", "learning_tags", "answer", "source_id"
        ])
        combined_norm = _normalize_vi_query(combined)
        combined_tokens = _tokenize_vi(combined)

        adjustment = 0.0
        overlap = q_tokens & combined_tokens
        if q_tokens:
            adjustment += min(0.10, len(overlap) / max(len(q_tokens), 1) * 0.12)

        intent = item.get("intent", "")
        category = item.get("category", "")
        audience = item.get("audience", "")

        if audience == "agent" and _is_customer_query_for_agent_content(norm_q):
            adjustment -= 0.18

        entity_rules = [
            ("zif", "zif", "zeo_product_catalog_overview"),
            ("pano", "pano", "zeo_product_catalog_overview"),
            ("oplus", "oplus", "zeo_product_catalog_overview"),
            ("npk", "npk", "product_lines"),
            ("huu co", "organic|huu_co|huu co", "product_lines"),
            ("toilet", "toilet|bon cau", "zeo_detergent_technology"),
            ("javen", "javen", "zeo_detergent_technology"),
        ]
        for query_anchor, positive_pattern, broad_intent in entity_rules:
            if query_anchor in norm_q:
                if re.search(positive_pattern, combined_norm):
                    adjustment += 0.16
                if intent == broad_intent:
                    adjustment -= 0.12

        if _has(r"(gioi thieu|so luoc|cong ty la gi|cty la gi|thuoc cong ty|homecare)", norm_q):
            if "company_overview" in intent:
                adjustment += 0.16
            if "address" in intent or "location" in intent:
                adjustment -= 0.18

        if _has(r"(dia chi|o dau|nha may|tru so|van phong|tai dau)", norm_q):
            if "address" in intent or "location" in intent:
                adjustment += 0.16
            if "company_overview" in intent and not _has(r"(gioi thieu|so luoc|la gi|thuoc)", norm_q):
                adjustment -= 0.06

        if _has(r"(so dien thoai|hotline|tong dai|lien he|call)", norm_q):
            if "contact" in intent or "hotline" in intent or "website" in intent:
                adjustment += 0.14
            if "address" in intent:
                adjustment -= 0.08

        if _has(r"(tik tok|tiktok|zalo|lazada|facebook)", norm_q) and _is_customer_query_for_agent_content(norm_q):
            if audience == "agent" or "content_style" in intent or "reels" in intent:
                adjustment -= 0.25

        if _has(r"\b(gia|bao gia|bang gia|bao nhieu tien|nhieu tien|gia ban|gia ca|xin gia)\b", norm_q):
            if "price" in intent or "sales" in category:
                adjustment += 0.12
            if "product_catalog" in intent:
                adjustment -= 0.08
        else:
            if "price_inquiry" in intent:
                adjustment -= 0.35
            if _has(r"(co\b.*\b(khong|hong|ko|k)|co nhung|cac dong|san pham gi|co san pham)", norm_q) and "overview" in intent:
                adjustment += 0.25

        # Priority trong Sheet
        adjustment += min(0.03, _safe_int(item.get("priority"), 0) / 1000)
        adjustment -= idx * 0.005

        item["vector_score"] = item["score"]
        item["rerank_adjustment"] = round(adjustment, 4)
        item["score"] = _clamp_score(item["score"] + adjustment)

    return sorted(parsed_results, key=lambda row: (row["score"], _safe_int(row.get("priority"))), reverse=True)


def _build_vi_embedding_query(query: str) -> str:
    """Mở rộng query tiếng Việt bằng no-accent + hint nhóm sản phẩm để RAG bám intent tốt hơn."""
    norm_q = _normalize_vi_query(query)
    variants = [query.strip(), norm_q]
    hints = []

    product_hints = [
        (r"(nuoc rua chen|nuoc rua bat|rua chen|rua bat|zif)", "nhom rua chen nuoc rua chen co san pham nao"),
        (r"(giat giu|nuoc giat|bot giat|giat quan ao|do giat)", "nhom giat giu nuoc giat bot giat co san pham nao"),
        (r"(nuoc lau san|lau san|nuoc lau nha|lau nha)", "nhom lau san nuoc lau san co san pham nao"),
        (r"(tay rua|ve sinh|javen|toilet|bon cau|lau kinh|xit tay|tay mau)", "nhom tay rua ve sinh co san pham nao"),
        (r"(phan bon|phan co bay|npk|huu co)", "danh muc phan bon cac dong phan bon co bay"),
    ]
    viewish = bool(re.search(r"(muon xem|xem ve|cho xem|tim hieu|hoi ve|thong tin ve|tu van|co.*gi|loai nao)", norm_q))
    if viewish:
        for pattern, hint in product_hints:
            if re.search(pattern, norm_q):
                hints.append(hint)

    for hint in hints:
        if hint not in variants:
            variants.append(hint)

    deduped = []
    seen = set()
    for variant in variants:
        variant = variant.strip()
        if variant and variant not in seen:
            deduped.append(variant)
            seen.add(variant)
    return " | ".join(deduped)


async def semantic_search(
    query: str,
    brand: str = "zeo",
    top_k: int = 5,
    category_filter: Optional[str] = None,
    exclude_fact_ids: Optional[list[str]] = None,
) -> dict:
    """
    Tìm kiếm ngữ nghĩa Hybrid:
      1. Thử Fast Lexical Search trong RAM trước (< 2ms). Nếu confidence cao -> Trả ngay!
      2. Nếu mơ hồ -> Gọi RediSearch Vector KNN (bge-m3).
      3. Nếu Ollama lỗi/timeout -> Fallback về top candidate từ Lexical Matcher.
    """
    await _ensure_cache_loaded(brand)
    b = brand.lower()

    # 1. Fast Lexical Matching trong RAM
    lexical_candidates = fast_lexical_search(
        query,
        b,
        top_k=top_k,
        exclude_fact_ids=exclude_fact_ids,
        category_filter=category_filter,
    )
    if lexical_candidates:
        best_lex = lexical_candidates[0]
        second_lex_score = lexical_candidates[1]["score"] if len(lexical_candidates) > 1 else 0.0
        margin = best_lex["score"] - second_lex_score

        # Agronomy answers pass through an additional evidence/category/crop
        # validator before customer send. A moderate lexical match is enough
        # to avoid a multi-second embedding call there; other domains retain
        # the stricter generic threshold.
        lexical_direct_threshold = 0.46 if category_filter == "agronomy" else 0.75
        if best_lex["score"] >= lexical_direct_threshold:
            return {
                "query": query,
                "brand": b,
                "confidence": "high" if best_lex["score"] >= 0.85 else "medium",
                "score": best_lex["score"],
                "score_margin": round(margin, 4),
                "intent": best_lex["intent"],
                "answer": best_lex["answer"],
                "answer_mode": best_lex["answer_mode"],
                "risk_level": best_lex["risk_level"],
                "category": best_lex["category"],
                "source_id": best_lex.get("source_id", ""),
                "priority": best_lex.get("priority", "0"),
                "retrieval_method": best_lex.get("retrieval_method", "in_memory_lexical"),
                "results": lexical_candidates,
            }

    # 2. RediSearch KNN Vector Search (Chỉ chạy khi lexical còn mơ hồ)
    cfg = _load_settings()
    rag_cfg = cfg["rag"]
    index_name = get_index_name(b, cfg)

    embed_query = _build_vi_embedding_query(query)
    vec = await embed_text(embed_query)

    # Nếu Ollama timeout/error -> Degraded mode dùng top lexical candidate
    if vec is None:
        logger.warning("Ollama embedding failed for '%s' -> Degraded mode to lexical search", query)
        if lexical_candidates and lexical_candidates[0]["score"] >= 0.45:
            best_lex = lexical_candidates[0]
            return {
                "query": query,
                "brand": b,
                "confidence": "medium",
                "score": best_lex["score"],
                "score_margin": 0.1,
                "intent": best_lex["intent"],
                "answer": best_lex["answer"],
                "answer_mode": best_lex["answer_mode"],
                "risk_level": best_lex["risk_level"],
                "category": best_lex["category"],
                "source_id": best_lex.get("source_id", ""),
                "retrieval_method": "degraded_lexical_fallback",
                "fallback_reason": "OLLAMA_TIMEOUT",
                "results": lexical_candidates,
            }
        return {
            "error": "Không thể tạo embedding cho query — Ollama timeout",
            "query": query,
            "confidence": "low",
            "score": 0.0,
            "fallback_reason": "OLLAMA_TIMEOUT",
        }

    query_bytes = vec_to_bytes(vec)
    r = await get_redis()
    try:
        filter_str = f"@category:{{{category_filter}}}" if category_filter else "*"
        results = await r.execute_command(
            "FT.SEARCH", index_name,
            f"({filter_str})=>[KNN {top_k} @embedding $vec AS __score]",
            "PARAMS", "2", "vec", query_bytes,
            "RETURN", "11", "intent", "answer", "answer_mode", "risk_level", "category", "source_id", "priority", "question_examples", "learning_tags", "audience", "__score",
            "SORTBY", "__score", "ASC",
            "DIALECT", "2",
        )
    except Exception as e:
        logger.error("RediSearch error: %s", e)
        if lexical_candidates:
            best_lex = lexical_candidates[0]
            return {
                "query": query,
                "brand": b,
                "confidence": "medium",
                "score": best_lex["score"],
                "intent": best_lex["intent"],
                "answer": best_lex["answer"],
                "answer_mode": best_lex["answer_mode"],
                "risk_level": best_lex["risk_level"],
                "category": best_lex["category"],
                "source_id": best_lex.get("source_id", ""),
                "retrieval_method": "degraded_redis_error_fallback",
                "fallback_reason": "REDIS_FAILED",
                "results": lexical_candidates,
            }
        return {"error": str(e), "query": query, "confidence": "low", "score": 0.0, "fallback_reason": "REDIS_FAILED"}

    if not results or results[0] == 0:
        if lexical_candidates and lexical_candidates[0]["score"] >= 0.45:
            best_lex = lexical_candidates[0]
            return {
                "query": query,
                "brand": b,
                "confidence": "medium",
                "score": best_lex["score"],
                "intent": best_lex["intent"],
                "answer": best_lex["answer"],
                "retrieval_method": "in_memory_lexical",
                "results": lexical_candidates,
            }
        return {
            "query": query,
            "brand": b,
            "confidence": "low",
            "score": 0.0,
            "intent": "",
            "answer": "",
            "results": [],
        }

    parsed_results = []
    i = 1
    exclude_set = set(exclude_fact_ids or [])
    while i < len(results):
        doc_key = results[i].decode() if isinstance(results[i], bytes) else results[i]
        fields_raw = results[i + 1] if i + 1 < len(results) else []
        i += 2

        fields = {}
        j = 0
        while j < len(fields_raw) - 1:
            k = fields_raw[j]
            v = fields_raw[j + 1]
            key = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            fields[key] = val
            j += 2

        intent = fields.get("intent", "")
        if intent in exclude_set:
            continue

        distance = float(fields.get("__score", 2.0))
        score = _cosine_to_confidence(distance)

        parsed_results.append({
            "intent": intent,
            "answer": fields.get("answer", ""),
            "answer_mode": fields.get("answer_mode", "direct"),
            "risk_level": fields.get("risk_level", "low"),
            "category": fields.get("category", "faq"),
            "source_id": fields.get("source_id", ""),
            "priority": fields.get("priority", "0"),
            "question_examples": fields.get("question_examples", ""),
            "learning_tags": fields.get("learning_tags", ""),
            "audience": fields.get("audience", ""),
            "score": score,
        })

    if not parsed_results:
        return {
            "query": query,
            "brand": b,
            "confidence": "low",
            "score": 0.0,
            "intent": "",
            "answer": "",
            "results": [],
        }

    parsed_results = _rerank_results(query, b, parsed_results)
    best = parsed_results[0]
    best_score = best["score"]
    second_score = parsed_results[1]["score"] if len(parsed_results) > 1 else 0.0
    margin = best_score - second_score

    high_thresh = rag_cfg["high_confidence_threshold"]
    med_thresh = rag_cfg["medium_confidence_threshold"]

    confidence = "low"
    if best_score >= high_thresh and margin >= 0.05:
        confidence = "high"
    elif best_score >= med_thresh:
        confidence = "medium"

    return {
        "query": query,
        "brand": b,
        "confidence": confidence,
        "score": best_score,
        "score_margin": round(margin, 4),
        "intent": best["intent"],
        "answer": best["answer"],
        "answer_mode": best["answer_mode"],
        "risk_level": best["risk_level"],
        "category": best["category"],
        "source_id": best.get("source_id", ""),
        "priority": best.get("priority", "0"),
        "vector_score": best.get("vector_score", best_score),
        "rerank_adjustment": best.get("rerank_adjustment", 0.0),
        "retrieval_method": "redis_vector_knn",
        "results": parsed_results,
    }


async def get_faq_by_intent(brand: str, intent: str) -> dict:
    """
    Lấy đúng một FAQ đã sync từ Google Sheet/Redis theo intent.
    Ưu tiên tìm trong In-Memory Cache trước (O(1), 0ms).
    """
    await _ensure_cache_loaded(brand)
    b = brand.lower()

    # 1. Kiểm tra In-Memory Cache trước
    if intent in _intent_map.get(b, {}):
        item = _intent_map[b][intent]
        return {
            "brand": b,
            "intent": item.get("intent", ""),
            "answer": item.get("answer", ""),
            "answer_mode": item.get("answer_mode", "direct"),
            "risk_level": item.get("risk_level", "low"),
            "category": item.get("category", "faq"),
            "source_id": item.get("source_id", ""),
            "question_examples": item.get("question_examples", ""),
            "learning_tags": item.get("learning_tags", ""),
            "profile_slots": item.get("profile_slots", ""),
            "escalation_policy": item.get("escalation_policy", ""),
            "priority": item.get("priority", "0"),
            "score": 1.0,
        }

    # 2. Fallback quét Redis nếu không có trong memory
    cfg = _load_settings()
    index_name = get_index_name(b, cfg)
    r = await get_redis()

    def _decode(value):
        return value.decode("utf-8") if isinstance(value, bytes) else value

    try:
        async for key in r.scan_iter(match=f"{index_name}:doc:*:{intent}", count=100):
            # pyrefly: ignore [not-async]
            fields_raw = await r.hgetall(key)
            fields = {}
            for k, v in fields_raw.items():
                field_name = _decode(k)
                if field_name == "embedding":
                    continue
                fields[field_name] = _decode(v)
            if fields.get("intent") != intent or not fields.get("answer"):
                continue
            return {
                "brand": b,
                "intent": fields.get("intent", ""),
                "answer": fields.get("answer", ""),
                "answer_mode": fields.get("answer_mode", "direct"),
                "risk_level": fields.get("risk_level", "low"),
                "category": fields.get("category", "faq"),
                "source_id": fields.get("source_id", ""),
                "question_examples": fields.get("question_examples", ""),
                "learning_tags": fields.get("learning_tags", ""),
                "profile_slots": fields.get("profile_slots", ""),
                "escalation_policy": fields.get("escalation_policy", ""),
                "priority": fields.get("priority", "0"),
                "score": 1.0,
            }
    except Exception as e:
        logger.warning("Redis intent lookup error (%s/%s): %s", b, intent, e)

    return {
        "brand": b,
        "intent": intent,
        "answer": "",
        "answer_mode": "direct",
        "risk_level": "low",
        "category": "faq",
        "source_id": "",
        "score": 0.0,
    }
