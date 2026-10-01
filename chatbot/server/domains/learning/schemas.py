"""
domains.learning.schemas — Pydantic DTOs cho Learning Queue Domain.
"""

from typing import List, Optional
from pydantic import BaseModel


class DismissQueueRequest(BaseModel):
    brand: str
    queue_key: str
    raw_value: str


class ApproveRequest(BaseModel):
    category: str
    intent: str
    question_examples: List[str]
    answer: str
    answer_mode: str = "direct"
    risk_level: str = "low"
