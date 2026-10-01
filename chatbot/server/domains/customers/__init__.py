"""
domains.customers — Customers Domain package.
"""

from .routes import router
from .service import get_customers_list, get_customer_session_detail, update_customer_profile

__all__ = ["router", "get_customers_list", "get_customer_session_detail", "update_customer_profile"]
