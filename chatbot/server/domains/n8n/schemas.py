"""
domains.n8n.schemas — Pydantic DTOs cho n8n Automation Domain.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class DeployRequest(BaseModel):
    workflow_file: str
    auto_resolve_conflict: bool = True
