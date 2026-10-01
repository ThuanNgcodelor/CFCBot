"""
knowledge_sync.py — Đọc dữ liệu FAQ từ Redis (JSON snapshot của n8n),
tạo vector embeddings cho mỗi item, và upsert vào Redis Vector Index (RediSearch).

Chạy thủ công: python knowledge_sync.py
Hoặc gọi qua API: POST /sync?brand=zeo
"""

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import redis.asyncio as aioredis

from embedder import embed_text, get_embed_dim, vec_to_bytes

logger = logging.getLogger(__name__)
_sync_runtime_status: dict[str, dict[str, Any]] = {"zeo": {}, "cfc": {}}


class KnowledgeSyncError(RuntimeError):
    """Fail-closed sync error with an explicit stage and checkpoint snapshot."""

    def __init__(self, stage: str, reason_code: str, checkpoints: Optional[dict[str, bool]] = None):
        self.stage = stage
        self.reason_code = reason_code
        self.checkpoints = dict(checkpoints or {})
        super().__init__(f"{stage}: {reason_code}")


def _load_settings() -> dict:
    settings_path = Path(__file__).parent / "settings.json"
    return json.loads(settings_path.read_text(encoding="utf-8"))


def normalize_vi(text: str) -> str:
    """Chuẩn hóa tiếng Việt về dạng không dấu, lowercase để ghép vào embedding text."""
    text = unicodedata.normalize("NFD", text)
    text = re.sub(r"[\u0300-\u036f]", "", text)
    text = text.replace("đ", "d").replace("Đ", "D")
    return text.lower()


def build_embed_text(item: dict) -> str:
    """
    Gom intent + question_examples + answer thành một đoạn text cho embedding.
    Ghép cả dạng gốc (có dấu) + dạng không dấu để model học cả 2 biến thể.
    """
    intent = str(item.get("intent", "")).replace("_", " ")
    answer = str(item.get("answer", ""))
    
    # question_examples có thể là string phân cách bởi ";" hoặc list
    raw_examples = item.get("question_examples", "")
    if isinstance(raw_examples, list):
        examples = [e.strip() for e in raw_examples if e.strip()]
    else:
        examples = [e.strip() for e in str(raw_examples).split(";") if e.strip()]

    parts = [intent] + examples + [answer]
    original_text = " | ".join(parts)
    no_accent_text = normalize_vi(original_text)
    
    # Kết hợp cả 2 để model nắm được cả 2 cách viết
    return f"{original_text} | {no_accent_text}"


def parse_snapshot(raw: str) -> list[dict]:
    """Parse JSON snapshot từ Redis (có thể là array hoặc có wrapper envelope)."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Không parse được snapshot JSON")
        return []
    
    if isinstance(data, list):
        return data
    
    # Dạng envelope: {"snapshot_json": "[...]", "updated_at": "..."}
    items_raw = data.get("snapshot_json") or data.get("knowledgeItems") or data.get("snapshot")
    if isinstance(items_raw, str):
        try:
            items = json.loads(items_raw)
        except json.JSONDecodeError:
            return []
    elif isinstance(items_raw, list):
        items = items_raw
    else:
        return []
    
    return items if isinstance(items, list) else []


def get_index_name(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_index_name"]
    return cfg["rag"]["zeo_index_name"]


def get_kb_key(brand: str, cfg: dict) -> str:
    if brand.lower() == "cfc":
        return cfg["rag"]["cfc_kb_key"]
    return cfg["rag"]["zeo_kb_key"]


def get_sync_runtime_status(brand: Optional[str] = None) -> dict[str, Any]:
    brands = [brand.lower()] if brand else ["zeo", "cfc"]
    return {
        "schema_version": 1,
        "brands": {current: dict(_sync_runtime_status.get(current) or {}) for current in brands if current in {"zeo", "cfc"}},
    }


async def ensure_index(r: aioredis.Redis, index_name: str, embed_dim: int) -> None:
    """Tạo RediSearch Vector Index nếu chưa có."""
    try:
        await r.execute_command("FT.INFO", index_name)
        logger.info("Index '%s' đã tồn tại.", index_name)
    except Exception:
        logger.info("Tạo mới index '%s' (dim=%d)...", index_name, embed_dim)
        # Schema: lưu doc dạng HASH
        # Field: embedding (VECTOR), intent (TEXT), brand (TAG), answer (TEXT), source_id (TAG), category (TAG)
        await r.execute_command(
            "FT.CREATE", index_name,
            "ON", "HASH",
            "PREFIX", "1", f"{index_name}:doc:",
            "SCHEMA",
            "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(embed_dim),
                "DISTANCE_METRIC", "COSINE",
            "intent", "TEXT", "WEIGHT", "2.0",
            "brand", "TAG",
            "category", "TAG",
            "answer_mode", "TAG",
            "risk_level", "TAG",
            "source_id", "TAG",
            "priority", "NUMERIC",
            "answer", "TEXT",
        )
        logger.info("Tạo index '%s' thành công.", index_name)


async def sync_brand(brand: str = "zeo", snapshot_key: Optional[str] = None) -> dict:
    """
    Đồng bộ dữ liệu FAQ từ Redis snapshot → Vector Index.
    """
    normalized_brand = str(brand or "").strip().lower()
    checkpoints = {
        "snapshot_validated": False,
        "vector_rebuilt": False,
        "hot_cache_refreshed": False,
    }
    if normalized_brand not in {"zeo", "cfc"}:
        raise KnowledgeSyncError("validation", "INVALID_BRAND", checkpoints)

    cfg = _load_settings()
    redis_cfg = cfg["redis"]
    active_kb_key = get_kb_key(normalized_brand, cfg)
    candidate_kb_key = active_kb_key.removesuffix(":active") + ":candidate"
    requested_kb_key = str(snapshot_key or active_kb_key).strip()
    if requested_kb_key not in {active_kb_key, candidate_kb_key}:
        raise KnowledgeSyncError("validation", "INVALID_SNAPSHOT_KEY", checkpoints)
    
    # Dùng kwargs riêng lẻ để tránh lỗi URL-encoding khi password có ký tự đặc biệt
    r = aioredis.Redis(
        host=redis_cfg["host"],
        port=int(redis_cfg["port"]),
        password=redis_cfg["password"],
        db=int(redis_cfg.get("db", 0)),
        decode_responses=False,
    )

    try:
        kb_key = requested_kb_key
        index_name = get_index_name(normalized_brand, cfg)
        embed_dim = get_embed_dim()

        # Đọc snapshot từ Redis
        raw = await r.get(kb_key)
        if not raw:
            raise KnowledgeSyncError("snapshot_validation", "SNAPSHOT_KEY_NOT_FOUND", checkpoints)
        
        items = parse_snapshot(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        if not items:
            raise KnowledgeSyncError("snapshot_validation", "SNAPSHOT_EMPTY_OR_INVALID", checkpoints)

        checkpoints["snapshot_validated"] = True
        raw_text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
        source_snapshot_hash = "sha256:" + hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

        # Prepare and validate every customer-facing vector before mutating the index.
        prepared_docs: list[tuple[str, dict[str, Any]]] = []
        skipped = 0
        active_doc_keys: set[str] = set()

        for item in items:
            # Lọc bỏ item không active, không có answer, audience=internal
            active = str(item.get("active", "true")).lower() in ("true", "1", "yes")
            if not active:
                skipped += 1
                continue
            if not item.get("answer") or not item.get("intent"):
                skipped += 1
                continue
            if str(item.get("audience", "customer")).lower() == "internal":
                skipped += 1
                continue

            doc_key = f"{index_name}:doc:{item.get('source_id', 'faq')}:{item.get('intent', 'unknown')}"
            embed_text_str = build_embed_text(item)
            try:
                vec = await embed_text(embed_text_str)
            except Exception as exc:
                raise KnowledgeSyncError(
                    "embedding",
                    "EMBEDDING_PROVIDER_ERROR",
                    checkpoints,
                ) from exc
            if vec is None:
                raise KnowledgeSyncError("embedding", "EMBEDDING_EMPTY", checkpoints)
            try:
                vector_length = len(vec)
            except TypeError as exc:
                raise KnowledgeSyncError("embedding", "EMBEDDING_INVALID", checkpoints) from exc
            if vector_length != embed_dim:
                raise KnowledgeSyncError("embedding", "EMBEDDING_DIMENSION_MISMATCH", checkpoints)
            
            mapping = {
                "embedding": vec_to_bytes(vec),
                "intent": str(item.get("intent", "")),
                "brand": str(item.get("brand", normalized_brand)).split("/")[0].strip(),
                "category": str(item.get("category", "faq")),
                "answer": str(item.get("answer", "")),
                "answer_mode": str(item.get("answer_mode", "direct")),
                "risk_level": str(item.get("risk_level", "low")),
                "source_id": str(item.get("source_id", "")),
                "question_examples": json.dumps(item.get("question_examples", ""), ensure_ascii=False),
                "learning_tags": json.dumps(item.get("learning_tags", ""), ensure_ascii=False),
                "profile_slots": json.dumps(item.get("profile_slots", ""), ensure_ascii=False),
                "escalation_policy": str(item.get("escalation_policy", "")),
                "priority": int(item.get("priority", 0)),
            }
            active_doc_keys.add(doc_key)
            prepared_docs.append((doc_key, mapping))

        if not prepared_docs:
            raise KnowledgeSyncError("snapshot_validation", "NO_CUSTOMER_ELIGIBLE_ITEMS", checkpoints)

        # Only now may the live vector index be changed.
        await ensure_index(r, index_name, embed_dim)
        for doc_key, mapping in prepared_docs:
            # pyrefly: ignore [not-async]
            await r.hset(doc_key, mapping=mapping)
        synced = len(prepared_docs)

        deleted_stale = 0
        async for key in r.scan_iter(match=f"{index_name}:doc:*", count=200):
            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            if key_str in active_doc_keys:
                continue
            await r.delete(key)
            deleted_stale += 1
            logger.info("✕ [%s] stale doc removed: %s", normalized_brand.upper(), key_str)
        checkpoints["vector_rebuilt"] = True

        from rag_search import refresh_knowledge_cache
        refresh_kwargs: dict[str, Any] = {"strict": True}
        if requested_kb_key != active_kb_key:
            refresh_kwargs["snapshot_key"] = requested_kb_key
        try:
            refresh_result = await refresh_knowledge_cache(normalized_brand, **refresh_kwargs)
        except Exception as exc:
            raise KnowledgeSyncError(
                "hot_cache_refresh",
                "HOT_CACHE_REFRESH_FAILED",
                checkpoints,
            ) from exc
        checkpoints["hot_cache_refreshed"] = True
        logger.info("✓ [%s] In-memory hot knowledge cache refreshed", normalized_brand.upper())
        completed_at = datetime.now(timezone.utc).isoformat()
        result = {
            "status": "ok",
            "complete": True,
            "brand": normalized_brand,
            "index": index_name,
            "snapshot_key": requested_kb_key,
            "source_snapshot_hash": source_snapshot_hash,
            **checkpoints,
            "synced": synced,
            "skipped": skipped,
            "errors": 0,
            "deleted_stale": deleted_stale,
            "total": len(items),
            "hot_cache": refresh_result,
        }
        _sync_runtime_status[normalized_brand] = {
            "status": "ok",
            "complete": True,
            "completed_at": completed_at,
            "snapshot_key": requested_kb_key,
            "source_snapshot_hash": source_snapshot_hash,
            "vector_source_snapshot_hash": source_snapshot_hash,
            "hot_cache_snapshot_hash": str(
                ((refresh_result.get("brands") or {}).get(normalized_brand) or {}).get("snapshot_hash") or ""
            ),
            "checkpoints": dict(checkpoints),
            "synced": synced,
        }
        setter = getattr(r, "set", None)
        if callable(setter):
            await setter(
                f"{normalized_brand}:knowledge:sync:last-complete",
                json.dumps(_sync_runtime_status[normalized_brand], ensure_ascii=False, separators=(",", ":")),
            )
        return result
    finally:
        await r.aclose()


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    
    print("=== Đồng bộ ZeO KB → Redis Vector ===")
    result = await sync_brand("zeo")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    print("\n=== Đồng bộ CFC KB → Redis Vector ===")
    result = await sync_brand("cfc")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
