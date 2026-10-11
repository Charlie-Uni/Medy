"""Bounded, thread-safe per-call bodies; encrypted audit storage only, never telemetry.

A logical call may include the adapter's temperature compatibility resend. Provider
attempts record SDK arguments, not HTTP headers, credentials or unverifiable wire bytes.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from medops.core.canonical import canonical_hash
from medops.core.errors import ErrorCode, InfrastructureError
from medops.infrastructure.llm.gateway import ModelCallReceipt, ModelRequest, ModelResponse

_ACTIVE: ContextVar[tuple[CallJournal, str] | None] = ContextVar("model_call_body_audit", default=None)


def _detach(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


class CallJournal:
    def __init__(self, *, max_calls: int = 128, max_bytes: int = 16 * 1024 * 1024) -> None:
        self._max_calls, self._max_bytes = max_calls, max_bytes
        self._entries: dict[str, dict[str, Any]] = {}
        self._bytes = 0
        self._blocked = False
        self._lock = threading.RLock()

    def ensure_complete(self) -> None:
        with self._lock:
            if self._blocked:
                raise InfrastructureError(ErrorCode.audit_unavailable, detail="model call journal capacity exceeded")

    @property
    def complete(self) -> bool:
        with self._lock:
            return not self._blocked

    def _replace(self, call_id: str, value: Mapping[str, Any]) -> None:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        old = self._entries.get(call_id)
        before = len(json.dumps(old, ensure_ascii=False, allow_nan=False).encode("utf-8")) if old else 0
        if self._bytes - before + len(encoded) > self._max_bytes:
            self._blocked = True
            self.ensure_complete()
        self._entries[call_id] = json.loads(encoded)
        self._bytes += len(encoded) - before

    @contextmanager
    def capture(self, request: ModelRequest) -> Iterator[None]:
        assert request.call is not None
        call_id = request.call.call_id
        with self._lock:
            self.ensure_complete()
            if call_id in self._entries or len(self._entries) >= self._max_calls:
                self._blocked = True
                self.ensure_complete()
            body = request.model_dump(mode="json")
            self._replace(
                call_id,
                {
                    "call_id": call_id,
                    "request": body,
                    "request_sha256": canonical_hash(body),
                    "provider_attempts": [],
                    "response": None,
                    "receipt": None,
                    "error_type": None,
                },
            )
        token = _ACTIVE.set((self, call_id))
        try:
            yield
        finally:
            _ACTIVE.reset(token)

    def provider_attempt(self, call_id: str, arguments: Mapping[str, Any], error_type: str | None = None) -> None:
        with self._lock:
            entry = _detach(self._entries[call_id])
            if error_type is not None:
                entry["provider_attempts"][-1]["error_type"] = error_type
            else:
                body = _detach(arguments)
                entry["provider_attempts"].append(
                    {"arguments": body, "sha256": canonical_hash(body), "error_type": None}
                )
            self._replace(call_id, entry)

    def provider_response(self, call_id: str, response: Mapping[str, Any], *, scope: str) -> None:
        with self._lock:
            entry = _detach(self._entries[call_id])
            body = _detach(response)
            entry["provider_attempts"][-1].update(
                response=body, response_sha256=canonical_hash(body), response_scope=scope
            )
            self._replace(call_id, entry)

    def finish(
        self, call_id: str, receipt: ModelCallReceipt, response: ModelResponse | None, error_type: str | None = None
    ) -> None:
        with self._lock:
            entry = _detach(self._entries[call_id])
            entry.update(
                receipt=receipt.model_dump(mode="json"),
                response=response.model_dump(mode="json") if response else None,
                error_type=error_type,
            )
            self._replace(call_id, entry)

    def snapshot(self) -> tuple[Mapping[str, Any], ...]:
        with self._lock:
            return tuple(_detach(list(self._entries.values())))


@contextmanager
def provider_attempt(arguments: Mapping[str, Any]) -> Iterator[None]:
    active = _ACTIVE.get()
    if active is not None:
        active[0].provider_attempt(active[1], arguments)
    try:
        yield
    except BaseException as exc:
        if active is not None:
            active[0].provider_attempt(active[1], {}, type(exc).__name__)
        raise


def record_provider_response(response: Any) -> None:
    active = _ACTIVE.get()
    if active is None:
        return
    if hasattr(response, "model_dump"):
        body, scope = response.model_dump(mode="json"), "sdk_completion_json"
    else:  # offline SDK stubs; never serialize repr() or arbitrary private object attributes
        body = {
            "id": getattr(response, "id", None),
            "model": getattr(response, "model", None),
            "system_fingerprint": getattr(response, "system_fingerprint", None),
            "choices": [
                {
                    "finish_reason": getattr(c, "finish_reason", None),
                    "message": {
                        "content": getattr(c.message, "content", None),
                        "refusal": getattr(c.message, "refusal", None),
                    },
                }
                for c in response.choices
            ],
        }
        scope = "offline_stub_selected_fields"
    active[0].provider_response(active[1], body, scope=scope)
