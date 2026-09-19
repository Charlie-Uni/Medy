"""trace_id generation and propagation via contextvars (INV-OBS-01).

`bind_trace_id()` scopes a trace id to the current task; asyncio tasks created inside the scope
inherit it (contextvars are copied on task creation). Nothing here records traces; that is the
observability adapter's job. The id format is 32 lowercase hex characters, the same width as a
W3C trace-id so it can be propagated unchanged.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from medops.core.errors import ErrorCode, InfrastructureError

_TRACE_ID = re.compile(r"^[0-9a-f]{32}$")
_current: ContextVar[str | None] = ContextVar("medops_trace_id", default=None)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def is_valid_trace_id(value: object) -> bool:
    return isinstance(value, str) and _TRACE_ID.fullmatch(value) is not None


def current_trace_id() -> str | None:
    return _current.get()


def require_trace_id() -> str:
    trace_id = _current.get()
    if trace_id is None:
        raise InfrastructureError(ErrorCode.internal_error, detail="no trace_id bound in this context", retryable=False)
    return trace_id


@contextmanager
def bind_trace_id(trace_id: str | None = None) -> Iterator[str]:
    """Bind `trace_id` for the duration of the block and restore the previous value afterwards.
    Only `None` generates a fresh id; any other value must be exactly 32 lowercase hex characters."""
    value = new_trace_id() if trace_id is None else trace_id
    if not is_valid_trace_id(value):
        raise ValueError("trace_id must be exactly 32 lowercase hex characters")
    token = _current.set(value)
    try:
        yield value
    finally:
        _current.reset(token)
