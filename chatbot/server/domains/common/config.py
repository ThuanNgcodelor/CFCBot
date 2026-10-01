"""
domains.common.config — Quản lý cấu hình settings.json và biến môi trường.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_settings_cache: Dict[str, Any] = {}


def get_settings_path() -> Path:
    return Path(__file__).resolve().parents[2] / "settings.json"


def auto_get_redis_env_pass() -> str:
    """Tự động đọc mật khẩu Redis từ file .env nếu có."""
    for p in [
        Path(__file__).resolve().parents[4] / "infra" / "redis" / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("REDIS_PASSWORD="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def get_cfg() -> dict:
    """Đọc cấu hình hệ thống hiện tại từ settings.json."""
    global _settings_cache
    cfg_path = get_settings_path()
    if cfg_path.exists():
        try:
            _settings_cache = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("Lỗi đọc settings.json: %s", e)
            _settings_cache = {}
    else:
        _settings_cache = {}

    # Tự động điền redis password nếu đang trống
    if not _settings_cache.get("redis", {}).get("password"):
        env_pass = auto_get_redis_env_pass()
        if env_pass:
            _settings_cache.setdefault("redis", {})["password"] = env_pass

    return _settings_cache


def load_settings() -> dict:
    return get_cfg()


def save_settings(new_cfg: dict) -> dict:
    """Lưu cấu hình mới vào settings.json và làm mới cache các module liên quan."""
    global _settings_cache
    cfg_path = get_settings_path()
    cfg_path.write_text(json.dumps(new_cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    _settings_cache = new_cfg

    # Refresh module caches
    try:
        import rag_search, embedder, ai_engine, telegram_notifier
        rag_search._redis_pool = None
        # pyrefly: ignore [missing-attribute]
        rag_search._settings = {}
        embedder._settings = {}
        ai_engine._settings = {}
        telegram_notifier._settings = {}
    except Exception:
        pass

    return new_cfg
