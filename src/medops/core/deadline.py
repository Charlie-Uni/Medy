"""Cooperative execution deadline shared by nested nodes and their I/O adapters.

The owner stays on the calling thread until its body and accepted child work have settled.
This is not a way to interrupt arbitrary Python/native code: non-cooperative inference belongs
in a terminable process. Cleanup and billing of an already-started call must still finish.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from medops.core.errors import ErrorCode, InfrastructureError


class DeadlineExceeded(InfrastructureError):
    def __init__(self) -> None:
        super().__init__(ErrorCode.dependency_timeout, detail="execution deadline exhausted", retryable=False)


@dataclass(frozen=True)
class Deadline:
    expires_at: float

    def remaining(self) -> float:
        remaining = self.expires_at - time.monotonic()
        if remaining <= 0:
            raise DeadlineExceeded()
        return remaining


CURRENT_DEADLINE: ContextVar[Deadline | None] = ContextVar("execution_deadline", default=None)
_ADMITTED: ContextVar[bool] = ContextVar("execution_admitted", default=False)
_SLOTS = threading.BoundedSemaphore(8)


def check_deadline() -> None:
    deadline = CURRENT_DEADLINE.get()
    if deadline is not None:
        deadline.remaining()


def remaining_timeout(limit_s: float) -> float:
    deadline = CURRENT_DEADLINE.get()
    return min(limit_s, deadline.remaining()) if deadline is not None else limit_s


@contextmanager
def execution_admission() -> Iterator[None]:
    """Eight root bodies, no executor queue; nested Skill nodes keep their parent's slot."""
    if _ADMITTED.get():
        yield
        return
    if not _SLOTS.acquire(timeout=remaining_timeout(0.25)):
        raise InfrastructureError(
            ErrorCode.dependency_timeout, detail="node execution capacity exhausted", retryable=False
        )
    token = _ADMITTED.set(True)
    try:
        check_deadline()
        yield
    finally:
        _ADMITTED.reset(token)
        _SLOTS.release()


@contextmanager
def deadline_scope(timeout_s: float) -> Iterator[Deadline]:
    parent = CURRENT_DEADLINE.get()
    expires = time.monotonic() + timeout_s
    deadline = Deadline(min(expires, parent.expires_at) if parent is not None else expires)
    token = CURRENT_DEADLINE.set(deadline)
    try:
        yield deadline
    finally:
        CURRENT_DEADLINE.reset(token)
