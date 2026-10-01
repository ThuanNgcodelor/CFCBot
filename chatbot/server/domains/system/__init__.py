"""
domains.system — System Domain package.
"""

from .routes import router
from .service import get_system_status, get_stats_today, save_daily_snapshot, get_weekly_analytics

__all__ = ["router", "get_system_status", "get_stats_today", "save_daily_snapshot", "get_weekly_analytics"]
