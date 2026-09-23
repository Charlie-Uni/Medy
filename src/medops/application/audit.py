"""Audit records (M3-07 first slice): one trace per request with its node spans, an escalation record whenever
the run did not answer, and user feedback bound to a trace. Written inside the request transaction; when the
audit write fails the request fails with `audit_unavailable` and no medical answer is returned (baseline 5.10).
Evidence text is never part of these records (INV-OBS-03)."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from medops.api.contracts import FeedbackReceipt, FeedbackRequest, FeedbackSignal
from medops.core.errors import BusinessError, ErrorCode, ErrorResponse, InfrastructureError
from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.contracts import NodeAttempt
from medops.harness.runtime import HarnessRun

FEEDBACK_ROUTE = "POST /v1/feedback"


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    run_id: str
    kind: str  # ask | task
    principal: str
    dept: Dept
    query: str
    outcome: str
    reason_codes: tuple[str, ...]
    versions: Mapping[str, Any]
    evidence_chunk_ids: tuple[str, ...]
    cited_chunk_ids: tuple[str, ...]
    flagged_chunk_ids: tuple[str, ...]
    model_calls: int
    tokens: int
    cost_usd: float
    duration_ms: float
    spans: tuple[NodeAttempt, ...]
    task_id: str | None = None


@dataclass(frozen=True)
class EscalationRecord:
    escalation_id: str
    trace_id: str
    principal: str
    dept: Dept
    reason_codes: tuple[str, ...]
    query: str
    evidence_chunk_ids: tuple[str, ...]
    verify_result: Mapping[str, Any] | None
    safety_result: Mapping[str, Any] | None
    policy_version: str
    detail: str


@dataclass(frozen=True)
class FeedbackRecord:
    feedback_id: str
    trace_id: str
    principal: str
    signal: str
    correction_text: str | None
    created_at: datetime


class TraceStore(Protocol):
    def record(self, trace: TraceRecord, escalation: EscalationRecord | None) -> None: ...

    def trace_principal(self, trace_id: str) -> str | None: ...

    def find_receipt(self, principal: str, route: str, key: str) -> tuple[str, Mapping[str, Any]] | None: ...

    def add_feedback(
        self, record: FeedbackRecord, idempotency: tuple[str, str, str, datetime, Mapping[str, Any]] | None
    ) -> None:
        """Insert feedback and, when given, the (route, key, request_hash, expires_at, receipt) idempotency row."""
        ...


def trace_from_run(
    run: HarnessRun,
    *,
    kind: str,
    user: UserContext,
    query: str,
    versions: VersionSet,
    outcome: str,
    model_calls: int,
    tokens: int,
    cost_usd: float,
    duration_ms: float,
    task_id: str | None = None,
) -> tuple[TraceRecord, EscalationRecord | None]:
    state = run.state
    esc = state.escalation
    codes = tuple(c.value for c in esc.reason_codes) if esc is not None else ()
    trace = TraceRecord(
        trace_id=state.trace_id,
        run_id=state.run_id,
        kind=kind,
        principal=user.user_id,
        dept=user.dept,
        query=query,
        outcome=outcome,
        reason_codes=codes,
        versions=versions.model_dump(mode="json"),
        evidence_chunk_ids=tuple(e.citation.chunk_id for e in state.evidence),
        cited_chunk_ids=tuple(c.chunk_id for c in state.answer.citations) if state.answer is not None else (),
        flagged_chunk_ids=tuple(run.flagged_evidence),
        model_calls=model_calls,
        tokens=tokens,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
        spans=run.attempts,
        task_id=task_id,
    )
    escalation = None
    if esc is not None:
        escalation = EscalationRecord(
            escalation_id=state.trace_id,
            trace_id=state.trace_id,
            principal=user.user_id,
            dept=user.dept,
            reason_codes=codes,
            query=esc.query,
            evidence_chunk_ids=tuple(esc.evidence_chunk_ids),
            verify_result=esc.verify_result.model_dump(mode="json") if esc.verify_result is not None else None,
            safety_result=esc.safety_result.model_dump(mode="json") if esc.safety_result is not None else None,
            policy_version=esc.policy_version,
            detail=esc.detail,
        )
    return trace, escalation


def record_or_fail_closed(store: TraceStore, trace: TraceRecord, escalation: EscalationRecord | None) -> None:
    """Baseline 5.10: no unaudited medical answer. Any store failure becomes `audit_unavailable` (retryable)."""
    try:
        store.record(trace, escalation)
    except InfrastructureError:
        raise
    except Exception as exc:  # noqa: BLE001 - the audit write failing must not leak internals either
        raise InfrastructureError(ErrorCode.audit_unavailable, detail=f"{type(exc).__name__}", retryable=True) from None


@dataclass
class FeedbackService:
    store: TraceStore
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    idempotency_ttl_s: int = 7 * 24 * 3600

    def submit(self, user: UserContext, request: FeedbackRequest, idempotency_key: str | None) -> FeedbackReceipt:
        from datetime import timedelta

        from medops.core.canonical import canonical_hash

        payload_hash = canonical_hash(request.model_dump(mode="json"))
        key = idempotency_key.strip() if idempotency_key is not None else None
        if key is not None:
            if not key or len(key) > 255:
                raise BusinessError(ErrorCode.invalid_request, "Idempotency-Key must be 1-255 characters")
            existing = self.store.find_receipt(user.user_id, FEEDBACK_ROUTE, key)
            if existing is not None:
                stored_hash, stored = existing
                if stored_hash != payload_hash:
                    raise BusinessError(
                        ErrorCode.idempotency_payload_mismatch, "same Idempotency-Key with a different payload"
                    )
                return FeedbackReceipt.model_validate(stored)
        owner = self.store.trace_principal(request.trace_id)
        if owner is None or owner != user.user_id:
            raise BusinessError(ErrorCode.not_found, "trace not found")  # visibility: the requesting principal's traces
        now = self.clock()
        record = FeedbackRecord(
            feedback_id=str(uuid.uuid4()),
            trace_id=request.trace_id,
            principal=user.user_id,
            signal=request.signal.value if isinstance(request.signal, FeedbackSignal) else str(request.signal),
            correction_text=request.correction_text,
            created_at=now,
        )
        receipt = FeedbackReceipt(feedback_id=record.feedback_id, trace_id=record.trace_id)
        idem = None
        if key is not None:
            idem = (
                FEEDBACK_ROUTE,
                key,
                payload_hash,
                now + timedelta(seconds=self.idempotency_ttl_s),
                receipt.model_dump(mode="json"),
            )
        try:
            self.store.add_feedback(record, idem)
        except IdempotencyRace:
            existing = self.store.find_receipt(user.user_id, FEEDBACK_ROUTE, key)  # type: ignore[arg-type]
            if existing is None or existing[0] != payload_hash:
                raise BusinessError(
                    ErrorCode.idempotency_payload_mismatch, "same Idempotency-Key with a different payload"
                ) from None
            return FeedbackReceipt.model_validate(existing[1])
        return receipt


class IdempotencyRace(Exception):
    pass


def public_error(exc: BaseException, trace_id: str | None) -> ErrorResponse:
    if isinstance(exc, InfrastructureError | BusinessError):
        return ErrorResponse(code=exc.code, message=exc.message, trace_id=trace_id, retryable=exc.retryable)
    return ErrorResponse(
        code=ErrorCode.internal_error, message="服务暂时不可用，请稍后重试", trace_id=trace_id, retryable=False
    )


# ------------------------------------------------------------------------------------ in-memory (tests)


@dataclass
class InMemoryTraceStore:
    traces: dict[str, TraceRecord] = field(default_factory=dict)
    escalations: dict[str, EscalationRecord] = field(default_factory=dict)
    feedback: list[FeedbackRecord] = field(default_factory=list)
    receipts: dict[tuple[str, str, str], tuple[str, Mapping[str, Any], datetime]] = field(default_factory=dict)
    fail_with: Exception | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def record(self, trace: TraceRecord, escalation: EscalationRecord | None) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        if trace.trace_id in self.traces:
            raise ValueError("trace already recorded")
        self.traces[trace.trace_id] = trace
        if escalation is not None:
            self.escalations[escalation.escalation_id] = escalation

    def trace_principal(self, trace_id: str) -> str | None:
        t = self.traces.get(trace_id)
        return t.principal if t else None

    def find_receipt(self, principal: str, route: str, key: str) -> tuple[str, Mapping[str, Any]] | None:
        row = self.receipts.get((principal, route, key))
        if row is None or row[2] <= self.clock():
            return None
        return row[0], row[1]

    def add_feedback(
        self, record: FeedbackRecord, idempotency: tuple[str, str, str, datetime, Mapping[str, Any]] | None
    ) -> None:
        if idempotency is not None:
            route, key, request_hash, expires, receipt = idempotency
            slot = (record.principal, route, key)
            if slot in self.receipts and self.receipts[slot][2] > self.clock():
                raise IdempotencyRace()
            self.receipts[slot] = (request_hash, receipt, expires)
        self.feedback.append(record)
