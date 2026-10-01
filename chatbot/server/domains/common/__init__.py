"""
domains.common — Shared Kernel chứa cấu hình chung, kết nối Redis và n8n client.
"""

from .config import get_cfg, get_settings_path, load_settings, save_settings, auto_get_redis_env_pass
from .db import get_redis_client, get_n8n_config, n8n_request

__all__ = [
    "get_cfg",
    "get_settings_path",
    "load_settings",
    "save_settings",
    "auto_get_redis_env_pass",
    "get_redis_client",
    "get_n8n_config",
    "n8n_request",
]
