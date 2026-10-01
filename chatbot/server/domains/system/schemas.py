"""
domains.system.schemas — Pydantic DTOs cho System Domain.
"""

from typing import Optional, Dict, Any
from pydantic import BaseModel


class SettingsUpdateRequest(BaseModel):
    redis: Optional[dict] = None
    ollama: Optional[dict] = None
    n8n: Optional[dict] = None
    rag: Optional[dict] = None
    ai_providers: Optional[dict] = None
    telegram: Optional[dict] = None
    shopee: Optional[dict] = None


class TelegramTestRequest(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    message: Optional[str] = None
