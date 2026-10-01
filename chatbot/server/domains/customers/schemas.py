"""
domains.customers.schemas — Pydantic DTOs cho Customers và Leads CRM.
"""

from typing import Optional, List
from pydantic import BaseModel


class CustomerUpdateRequest(BaseModel):
    fb_name: Optional[str] = None
    phone: Optional[str] = None
    area: Optional[str] = None
    lead_stage: Optional[str] = None
    last_intent: Optional[str] = None
    admin_notes: Optional[str] = None
    admin_tags: Optional[List[str]] = None
