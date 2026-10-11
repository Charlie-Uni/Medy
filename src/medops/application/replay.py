"""Explicit current-fact diagnosis with fresh execution IDs and restricted source input.

Original-condition mode fails before model admission: a selected evidence snapshot
cannot restore corpus statistics, indexes or an attested loaded build. No escalation
is created by a diagnostic replay; current permissions always govern fact access.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from medops.application.audit import ReplayRecord, TraceStore, trace_from_run
from medops.application.contracts import (
    AskRequest,
    HistoricalRequest,
    ReplayReport,
    ReplayRequest,
    ReplaySide,
    TracePayloadResponse,
)
from medops.application.execution_audit import ExecutionAuditWriter
from medops.application.payloads import payloads_from_run
from medops.application.replay_inputs import compare_conditions, payload_sections, saved_input, validate_call_records
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import ReasonCode
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.domain.state import VersionSet
from medops.harness.audit import ExecutionAudit
from medops.harness.dependencies import HarnessDeps
from medops.harness.runtime import HarnessRun, initial_state, run_ask
from medops.infrastructure.llm.meter import MeteredGateway

DIFF_FIELDS = ("outcome", "reason_codes", "cited_chunk_ids", "evidence_chunk_ids")


def _side(
    trace_id: str,
    run_id: str,
    outcome: str,
    codes: tuple[str, ...],
    cited: tuple[str, ...],
    evidence: tuple[str, ...],
    versions: VersionSet,
    query_context: QueryContext,
) -> ReplaySide:
    return ReplaySide(
        trace_id=trace_id,
        run_id=run_id,
        outcome=outcome,
        reason_codes=tuple(ReasonCode(c) for c in codes),
        cited_chunk_ids=cited,
        evidence_chunk_ids=evidence,
        versions=versions,
        query_context=query_context,
    )


def outcome_of(run: HarnessRun) -> str:
    """Same mapping as the public ask response: refused for policy refusals, escalated otherwise."""
    from medops.domain.common import REFUSAL_CODES

    if run.state.answer is not None:
        return "answered"
    esc = run.state.escalation
    assert esc is not None
    return "refused" if set(esc.reason_codes) <= REFUSAL_CODES else "escalated"


@dataclass
class ReplayService:
    store: TraceStore
    build_deps: Callable[[UserContext, QueryContext, AskRequest], tuple[HarnessDeps, VersionSet]]
    resolve_user: Callable[[str], UserContext | None]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    payload_writer: Any = None  # PayloadWriter | None (DEC-013): the replay's own payload, same transaction
    load_payload: Callable[[UserContext, str, str], TracePayloadResponse] | None = None

    def replay(self, admin: UserContext, source_trace_id: str, request: ReplayRequest) -> ReplayReport:
        source = self.store.read_trace(source_trace_id)
        if source is None or source.kind == "replay":
            raise BusinessError(ErrorCode.not_found, "trace not found")
        if source.kind != "ask":
            raise BusinessError(
                ErrorCode.invalid_request,
                "this replay supports Ask traces only; Task/MCP need their original typed input",
            )
        if source.query_context is None:
            raise BusinessError(
                ErrorCode.invalid_request,
                "source trace has no saved query context; historical input cannot be inferred",
            )
        user = self.resolve_user(source.principal)
        if user is None or user.dept is not source.dept:
            raise BusinessError(
                ErrorCode.invalid_request, "the trace's principal is no longer provisioned for that department"
            )
        if request.mode == "original_conditions":
            raise BusinessError(
                ErrorCode.version_conflict,
                "original conditions unavailable: archived corpus/index and attested build required",
            )
        original_payloads = {}
        restored = None
        if self.load_payload is not None:
            try:
                original_payloads = payload_sections(
                    self.load_payload(admin, source.trace_id, ("diagnostic replay: " + request.reason)[:500])
                )
                restored = saved_input(original_payloads, source)
                validate_call_records(original_payloads)
                compare_conditions(original_payloads, original_payloads, input_complete=restored is not None)
            except BusinessError as exc:
                if exc.code != ErrorCode.not_found:
                    raise
            except (ValueError, TypeError, KeyError) as exc:
                raise BusinessError(ErrorCode.invalid_request, "source execution payload is invalid") from exc
        body = (
            restored[0]
            if restored is not None
            else AskRequest(
                query=source.query,
                historical=HistoricalRequest(as_of=source.query_context.as_of)
                if source.query_context.historical_requested
                else None,
            )
        )
        replay_trace_id = uuid.uuid4().hex
        replay_run_id = uuid.uuid4().hex  # independent of the source run: no operation key can be reused
        built, versions = self.build_deps(user, source.query_context, body)
        deps = replace(built, audit=ExecutionAudit())
        state = initial_state(
            user=user,
            query=source.query,
            versions=versions,
            trace_id=replay_trace_id,
            run_id=replay_run_id,
            query_context=source.query_context,
            session_entities=restored[1].session_entities if restored is not None else (),
            token_limit=restored[1].token_limit if restored is not None else 12_000,
        )
        started = self.clock()
        run = run_ask(state, deps, recursion_limit=restored[1].recursion_limit if restored is not None else 12)
        outcome = outcome_of(run)
        meter = deps.gateway if isinstance(deps.gateway, MeteredGateway) else None
        trace, _escalation = trace_from_run(
            run,
            kind="replay",
            user=user,
            query=source.query,
            versions=versions,
            outcome=outcome,
            model_calls=meter.calls if meter else 0,
            tokens=meter.tokens if meter else run.state.budget.used,
            cost_usd=meter.cost_usd if meter else 0.0,
            duration_ms=max((self.clock() - started).total_seconds() * 1000, 0.0),
        )
        payloads = payloads_from_run(run, query=trace.query, request=body.model_dump(mode="json"), audit=deps.audit)
        ExecutionAuditWriter(self.store, self.payload_writer).record(trace, None, node="replay", payloads=payloads)
        source_versions = VersionSet.model_validate(source.versions)
        src = _side(
            source.trace_id,
            source.run_id,
            source.outcome,
            source.reason_codes,
            source.cited_chunk_ids,
            source.evidence_chunk_ids,
            source_versions,
            source.query_context,
        )
        rep = _side(
            trace.trace_id,
            trace.run_id,
            trace.outcome,
            trace.reason_codes,
            trace.cited_chunk_ids,
            trace.evidence_chunk_ids,
            versions,  # the versions the replay actually ran with (routed per principal, M4-09), not the base set
            source.query_context,
        )
        changed = tuple(f for f in DIFF_FIELDS if getattr(src, f) != getattr(rep, f))
        report = ReplayReport(
            replay_id=str(uuid.uuid4()),
            source=src,
            replay=rep,
            versions_match=source_versions == versions,
            mode=request.mode,
            conditions=compare_conditions(original_payloads, payloads, input_complete=restored is not None),
            changed=changed,
            created_at=self.clock(),
        )
        record = ReplayRecord(
            replay_id=report.replay_id,
            source_trace_id=source.trace_id,
            replay_trace_id=trace.trace_id,
            replay_run_id=replay_run_id,
            requested_by=admin.user_id,
            reason=request.reason,
            versions_match=report.versions_match,
            changed=changed,
            report=report.model_dump(mode="json"),
        )
        try:
            self.store.record_replay(record)
        except Exception as exc:  # noqa: BLE001 - the report shares the caller's audit transaction
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__, retryable=True) from None
        return report
