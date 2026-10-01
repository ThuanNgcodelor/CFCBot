"""
document_ingestor.py — Engine Tự Học từ Tài Liệu Markdown (.md) & Text (.txt)
Chức năng:
  1. Đọc và phân mảnh văn bản thông minh (Heading-aware Semantic Chunking: #, ##, ###).
  2. Tạo vector ngữ nghĩa 1024-dim qua bge-m3.
  3. Lưu vào RediSearch Document Vector Index (zeo:vec:docs, cfc:vec:docs).
  4. Tìm kiếm ngữ nghĩa tài liệu (Document Search) và trích xuất đoạn văn phù hợp.
  5. Tự động chuyển đổi tài liệu dài thành bộ câu hỏi - đáp FAQ qua AI.
"""

import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis

from ai_engine import generate_ai_text
from embedder import embed_text, get_embed_dim, vec_to_bytes

logger = logging.getLogger(__name__)

_settings: dict = {}


def _load_settings() -> dict:
    global _settings
    cfg_path = Path(__file__).parent / "settings.json"
    if cfg_path.exists():
        _settings = json.loads(cfg_path.read_text(encoding="utf-8"))
    return _settings


def _get_redis() -> aioredis.Redis:
    cfg = _load_settings().get("redis", {})
    return aioredis.Redis(
        host=cfg.get("host", "127.0.0.1"),
        port=int(cfg.get("port", 6379)),
        password=cfg.get("password", "") or None,
        db=int(cfg.get("db", 0)),
        decode_responses=False,
    )


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "d").lower()


def _chunk_id(source_path: str, ordinal: int, text: str) -> str:
    h = hashlib.sha256(f"{source_path}:{ordinal}:{text[:50]}".encode()).hexdigest()[:12]
    return f"c_{h}"


def split_markdown(text: str, source_path: str, max_chars: int = 1500, overlap: int = 150) -> list[dict]:
    """Tách Markdown thông minh theo tiêu đề và đoạn văn bản."""
    body = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if body.startswith("---\n"):
        end = body.find("\n---", 4)
        if end >= 0:
            body = body[end + 4:].lstrip("\n")

    heading = Path(source_path).stem
    parts, current = [], []
    for line in body.split("\n"):
        hit = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if hit:
            if current:
                parts.append((heading, "\n".join(current).strip()))
                current = []
            heading = hit.group(1).strip()
        else:
            current.append(line)
    if current:
        parts.append((heading, "\n".join(current).strip()))

    chunks: list[dict] = []
    ordinal = 0
    for title, section in parts:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", section) if p.strip()]
        buffer = ""
        for paragraph in paragraphs:
            candidate = paragraph if not buffer else buffer + "\n\n" + paragraph
            if len(candidate) <= max_chars:
                buffer = candidate
                continue
            if buffer:
                cid = _chunk_id(source_path, ordinal, buffer)
                chunks.append({
                    "chunk_id": cid,
                    "source_file": Path(source_path).name,
                    "heading": title,
                    "content": buffer,
                })
                ordinal += 1
                tail = buffer[-overlap:].strip() if overlap else ""
                buffer = (tail + "\n\n" + paragraph).strip() if tail else paragraph

        if buffer:
            cid = _chunk_id(source_path, ordinal, buffer)
            chunks.append({
                "chunk_id": cid,
                "source_file": Path(source_path).name,
                "heading": title,
                "content": buffer,
            })
            ordinal += 1

    return chunks


async def ensure_doc_index(r: aioredis.Redis, index_name: str, embed_dim: int):
    """Tạo RediSearch Document Vector Index nếu chưa có."""
    try:
        await r.execute_command("FT.INFO", index_name)
    except Exception:
        logger.info("Tạo Document Vector Index '%s' (dim=%d)...", index_name, embed_dim)
        await r.execute_command(
            "FT.CREATE", index_name,
            "ON", "HASH",
            "PREFIX", "1", f"{index_name}:doc:",
            "SCHEMA",
            "embedding", "VECTOR", "HNSW", "6",
                "TYPE", "FLOAT32",
                "DIM", str(embed_dim),
                "DISTANCE_METRIC", "COSINE",
            "heading", "TEXT", "WEIGHT", "2.0",
            "content", "TEXT",
            "source_file", "TAG",
            "brand", "TAG",
        )


async def ingest_markdown_file(file_path: Path, brand: Optional[str] = None) -> dict:
    """Nạp 1 file Markdown/Text vào Redis Vector Store."""
    if not file_path.exists():
        return {"error": f"File {file_path} không tồn tại", "synced": 0}

    filename = file_path.name.lower()
    auto_brand = brand or ("cfc" if "cfc" in filename or "co_bay" in filename else "zeo")
    index_name = f"{auto_brand.lower()}:vec:docs"

    text = file_path.read_text(encoding="utf-8")
    chunks = split_markdown(text, str(file_path))

    r = _get_redis()
    try:
        embed_dim = get_embed_dim()
        await ensure_doc_index(r, index_name, embed_dim)

        synced = 0
        for chunk in chunks:
            embed_str = f"{chunk['heading']} | {chunk['content']} | {_fold(chunk['heading'])} | {_fold(chunk['content'])}"
            vec = await embed_text(embed_str)
            if not vec:
                continue

            doc_key = f"{index_name}:doc:{chunk['source_file']}:{chunk['chunk_id']}"
            # pyrefly: ignore [not-async]
            await r.hset(doc_key, mapping={
                "embedding": vec_to_bytes(vec),
                "heading": chunk["heading"],
                "content": chunk["content"],
                "source_file": chunk["source_file"],
                "brand": auto_brand.upper(),
            })
            synced += 1

        return {
            "success": True,
            "file": file_path.name,
            "brand": auto_brand.upper(),
            "index": index_name,
            "chunks_count": len(chunks),
            "synced_count": synced,
        }
    finally:
        await r.aclose()


async def ingest_knowledge_folder(folder_path: Optional[Path] = None) -> dict:
    """Quét toàn bộ thư mục knowledge/ và nạp tất cả file .md, .txt vào Redis."""
    target_dir = folder_path or (Path(__file__).resolve().parents[2] / "knowledge")
    if not target_dir.exists():
        target_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for file in target_dir.glob("*"):
        if file.suffix.lower() in [".md", ".txt"]:
            res = await ingest_markdown_file(file)
            results.append(res)

    return {"total_files": len(results), "details": results}


async def search_documents(query: str, brand: str = "zeo", top_k: int = 3) -> list[dict]:
    """Tìm kiếm đoạn văn bản trong tài liệu Markdown gần nhất với câu hỏi."""
    index_name = f"{brand.lower()}:vec:docs"
    vec = await embed_text(query)
    if not vec:
        return []

    r = _get_redis()
    try:
        query_bytes = vec_to_bytes(vec)
        results = await r.execute_command(
            "FT.SEARCH", index_name,
            f"(*)=>[KNN {top_k} @embedding $vec AS __score]",
            "PARAMS", "2", "vec", query_bytes,
            "RETURN", "4", "heading", "content", "source_file", "__score",
            "SORTBY", "__score", "ASC",
            "DIALECT", "2",
        )

        if not results or results[0] == 0:
            return []

        parsed = []
        i = 1
        while i < len(results):
            fields_raw = results[i + 1] if i + 1 < len(results) else []
            i += 2
            fields = {}
            j = 0
            while j < len(fields_raw) - 1:
                k = fields_raw[j].decode() if isinstance(fields_raw[j], bytes) else fields_raw[j]
                v = fields_raw[j + 1].decode() if isinstance(fields_raw[j + 1], bytes) else fields_raw[j + 1]
                fields[k] = v
                j += 2

            distance = float(fields.get("__score", 2.0))
            score = round(max(0.0, min(1.0, 1.0 - (distance / 2.0))), 4)
            parsed.append({
                "heading": fields.get("heading", ""),
                "content": fields.get("content", ""),
                "source_file": fields.get("source_file", ""),
                "score": score,
            })
        return parsed
    except Exception as e:
        logger.warning("Lỗi khi tìm kiếm tài liệu trên %s: %s", index_name, e)
        return []
    finally:
        await r.aclose()


async def ai_extract_faqs(document_text: str, brand: str = "zeo") -> list[dict]:
    """Dùng AI tự động trích xuất các cặp câu hỏi - câu trả lời FAQ chuẩn từ tài liệu dài."""
    prompt = f"""
Hãy đọc kỹ tài liệu sau đây và trích xuất ra 5 đến 8 cặp Hỏi - Đáp (FAQ) thông dụng nhất mà khách hàng thường hỏi trên Messenger.
Yêu cầu:
- Tự thêm các câu hỏi mẫu biến thể (kể cả câu không dấu, viết tắt: vd: 'gia sao shop', 'co ship k').
- Câu trả lời chuẩn mực theo văn phong CSKH thân thiện, dùng 'bạn' và 'mình'.
- Trả về duy nhất định dạng JSON mảng danh sách [ {{"intent": "...", "question_examples": "cau 1; cau 2; cau 3", "answer": "..."}} ].

Tài liệu:
{document_text[:3500]}
"""
    res = await generate_ai_text(
        prompt=prompt,
        system_prompt=f"Bạn là chuyên gia trích xuất FAQ CSKH cho thương hiệu {brand.upper()}.",
    )
    if res.get("success"):
        try:
            raw = res.get("text", "")
            if "```" in raw:
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE).strip()
            start, end = raw.find("["), raw.rfind("]")
            if start >= 0 and end > start:
                return json.loads(raw[start:end + 1])
        except Exception as e:
            logger.warning("Không parse được JSON FAQ từ AI: %s", e)
    return []
