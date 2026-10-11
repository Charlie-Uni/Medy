"""Execution ownership and a context-local receipt channel; no shared last-result or exception mutation."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from medops.core.tracing import current_trace_id
from medops.infrastructure.llm.gateway import ModelCall, ModelCallReceipt, ModelRequest


@dataclass(frozen=True)
class CallScope:
    run_id: str | None = None
    attempt_id: str | None = None


@dataclass
class CallCapture:
    call_id: str
    receipt: ModelCallReceipt | None = None


_SCOPE: ContextVar[CallScope | None] = ContextVar("model_call_scope", default=None)
_CAPTURE: ContextVar[CallCapture | None] = ContextVar("model_call_capture", default=None)


@contextmanager
def call_scope(*, run_id: str | None = None, attempt_id: str | None = None) -> Iterator[None]:
    parent = _SCOPE.get() or CallScope()
    attempt = parent.attempt_id
    if attempt_id is not None:
        attempt = f"{attempt}/{attempt_id}" if attempt else attempt_id
    token = _SCOPE.set(CallScope(run_id=run_id or parent.run_id, attempt_id=attempt))
    try:
        yield
    finally:
        _SCOPE.reset(token)


def new_call(request: ModelRequest, provider: str) -> ModelCall:
    scope = _SCOPE.get() or CallScope()
    trace_id = current_trace_id()
    return ModelCall(
        call_id=str(uuid.uuid4()),
        trace_id=trace_id,
        run_id=scope.run_id or trace_id,
        attempt_id=scope.attempt_id,
        purpose=request.purpose,
        requested_model=request.model_id,
        provider=provider,
    )


@contextmanager
def capture_call(call_id: str) -> Iterator[CallCapture]:
    parent = _CAPTURE.get()
    capture = CallCapture(call_id)
    token = _CAPTURE.set(capture)
    try:
        yield capture
    finally:
        _CAPTURE.reset(token)
        if parent is not None and parent.call_id == call_id and capture.receipt is not None:
            parent.receipt = capture.receipt


def publish_receipt(receipt: ModelCallReceipt) -> None:
    capture = _CAPTURE.get()
    if capture is not None:
        if capture.call_id != receipt.call.call_id:
            raise ValueError("model receipt belongs to a different call")
        capture.receipt = receipt
