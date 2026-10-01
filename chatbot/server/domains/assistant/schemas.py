"""
domains.assistant.schemas — Pydantic DTOs cho Trợ Lý AI.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class AssistantChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = []
    brand: Optional[str] = "all"


class QuickPromptItem(BaseModel):
    label: str
    query: str
