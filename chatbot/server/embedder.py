"""
embedder.py — Tạo vector embeddings thông qua Ollama local.
Model mặc định: bge-m3 (đa ngôn ngữ, hiểu tiếng Việt rất tốt kể cả không dấu).
Fallback: qwen2.5:7b-instruct (đã có sẵn trong Ollama của bạn).
"""

import json
import logging
from pathlib import Path
from typing import Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)

_settings: dict = {}


def _load_settings() -> dict:
    global _settings
    if not _settings:
        settings_path = Path(__file__).parent / "settings.json"
        _settings = json.loads(settings_path.read_text(encoding="utf-8"))
    return _settings


def _ollama_cfg() -> dict:
    return _load_settings()["ollama"]


def get_embed_dim() -> int:
    return _ollama_cfg()["embed_dim"]


async def embed_text(text: str, model: Optional[str] = None) -> Optional[list[float]]:
    """
    Gọi Ollama API lấy embedding vector cho một đoạn text.
    Trả về list[float] hoặc None nếu lỗi.
    """
    cfg = _ollama_cfg()
    embed_model = model or cfg["embed_model"]
    url = f"{cfg['base_url']}/api/embed"

    payload = {"model": embed_model, "input": text}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Ollama /api/embed trả về {"embeddings": [[...]], "model": "..."}
            embeddings = data.get("embeddings") or data.get("embedding")
            if embeddings is None:
                logger.error("Ollama trả về không có field 'embeddings': %s", data)
                return None
            # Nếu dạng [[...]] thì lấy phần tử đầu
            vec = embeddings[0] if isinstance(embeddings[0], list) else embeddings
            return vec
    except httpx.HTTPStatusError as e:
        # Nếu model chưa có → thử fallback model
        if e.response.status_code == 404 and embed_model != cfg.get("fallback_embed_model"):
            logger.warning(
                "Model %s chưa pull về Ollama. Thử fallback: %s",
                embed_model,
                cfg.get("fallback_embed_model"),
            )
            return await embed_text(text, model=cfg.get("fallback_embed_model"))
        logger.error("Ollama HTTP error: %s", e)
        return None
    except Exception as e:
        logger.error("Embed lỗi: %s", e)
        return None


def vec_to_bytes(vec: list[float]) -> bytes:
    """Chuyển vector sang bytes để lưu vào Redis VECTOR field."""
    return np.array(vec, dtype=np.float32).tobytes()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Tính cosine similarity giữa 2 vector (dự phòng khi cần)."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
