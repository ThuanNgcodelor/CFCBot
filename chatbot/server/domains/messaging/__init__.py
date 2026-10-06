"""Durable inbound bundling, response outbox, and sales handoff domain."""

from .routes import router
from .service import get_messaging_runtime

__all__ = ["router", "get_messaging_runtime"]
