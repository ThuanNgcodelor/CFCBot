"""
domains.knowledge.schemas — Pydantic DTOs cho Knowledge, Google Sheets và Documents.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class SheetTabsRequest(BaseModel):
    sheet_url: str
    api_key: Optional[str] = None


class SheetPreviewRequest(BaseModel):
    sheet_url: str
    sheet_name: Optional[str] = None
    target_type: str = "faq"
    brand: str = "zeo"
    api_key: Optional[str] = None


class SheetSyncRequest(BaseModel):
    sheet_url: str
    sheet_name: Optional[str] = None
    target_type: str = "faq"
    brand: str = "zeo"
    api_key: Optional[str] = None


class ExtractFaqRequest(BaseModel):
    filename: str
    brand: str = "zeo"


class ShopeeProduct(BaseModel):
    brand: str
    name: str
    variant: Optional[str] = ""
    price: Optional[str] = ""
    promotion: Optional[str] = ""
    link: str
    keywords: Optional[List[str]] = []
