"""
domains.knowledge — Knowledge Domain package.
"""

from .routes import router
from .service import sync_shopee_from_sheet

__all__ = ["router", "sync_shopee_from_sheet"]
