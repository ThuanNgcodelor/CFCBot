"""Context-local guard for evaluation runs that must not contact operators."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator


_EXTERNAL_SIDE_EFFECTS_ALLOWED: ContextVar[bool] = ContextVar(
    "external_side_effects_allowed", default=True
)


@contextmanager
def block_external_side_effects() -> Iterator[None]:
    """Block outbound side effects in this context and inherited async tasks."""
    token = _EXTERNAL_SIDE_EFFECTS_ALLOWED.set(False)
    try:
        yield
    finally:
        _EXTERNAL_SIDE_EFFECTS_ALLOWED.reset(token)


def external_side_effects_allowed() -> bool:
    return _EXTERNAL_SIDE_EFFECTS_ALLOWED.get()
