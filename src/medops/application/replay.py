"""Single-trace replay (M3-08): run the source trace's question again under the original principal's current
identity, this deployment's pinned versions and a fresh `replay_run_id`, then diff outcome, reason codes and
citations against the stored trace. The replay is recorded as its own trace (kind `replay`); it never creates
a human escalation and never reuses an operation-key result of the production run (different run id)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from medops.api.contracts import ReplayReport, ReplayRequest, ReplaySide
from medops.application.audit import ReplayRecord, TraceStore, record_or_fail_closed, trace_from_run
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import ReasonCode
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
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
) -> ReplaySide:
    return ReplaySide(
        trace_id=trace_id,
        run_id=run_id,
        outcome=outcome,
        reason_codes=tuple(ReasonCode(c) for c in codes),
        cited_chunk_ids=cited,
        evidence_chunk_ids=evidence,
        versions=versions,
    )


def outcome_of(run: HarnessRun) -> str:
    """Same mapping as the public ask response: refused for policy refusals, escalated otherwise."""
    from medops.api.responses import REFUSAL_CODES

    if run.state.answer is not None:
        return "answered"
    esc = run.state.escalation
    assert esc is not None
    return "refused" if set(esc.reason_codes) <= REFUSAL_CODES else "escalated"


@dataclass
class ReplayService:
    store: TraceStore
    versions: VersionSet
    build_deps: Callable[[UserContext], HarnessDeps]
    resolve_user: Callable[[str], UserContext | None]
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    payload_writer: Any = None  # PayloadWriter | None (DEC-013): the replay's own payload, same transaction
    versions_for: Callable[[UserContext], VersionSet] | None = None  # M4-09: the replayed principal's routed versions

    def replay(self, admin: UserContext, source_trace_id: str, request: ReplayRequest) -> ReplayReport:
        source = self.store.read_trace(source_trace_id)
        if source is None or source.kind == "replay":
            raise BusinessError(ErrorCode.not_found, "trace not found")
        user = self.resolve_user(source.principal)
        if user is None or user.dept is not source.dept:
            raise BusinessError(
                ErrorCode.invalid_request, "the trace's principal is no longer provisioned for that department"
            )
        replay_trace_id = uuid.uuid4().hex
        replay_run_id = uuid.uuid4().hex  # independent of the source run: no operation key can be reused
        deps = self.build_deps(user)
        versions = self.versions_for(user) if self.versions_for is not None else self.versions
        state = initial_state(
            user=user, query=source.query, versions=versions, trace_id=replay_trace_id, run_id=replay_run_id
        )
        started = self.clock()
        run = run_ask(state, deps)
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
        record_or_fail_closed(self.store, trace, None)  # a replay is diagnostic: no human escalation
        if self.payload_writer is not None:
            self.payload_writer.record_run(run, query=trace.query, node="replay")
        source_versions = VersionSet.model_validate(source.versions)
        src = _side(
            source.trace_id,
            source.run_id,
            source.outcome,
            source.reason_codes,
            source.cited_chunk_ids,
            source.evidence_chunk_ids,
            source_versions,
        )
        rep = _side(
            trace.trace_id,
            trace.run_id,
            trace.outcome,
            trace.reason_codes,
            trace.cited_chunk_ids,
            trace.evidence_chunk_ids,
            versions,  # the versions the replay actually ran with (routed per principal, M4-09), not the base set
        )
        changed = tuple(f for f in DIFF_FIELDS if getattr(src, f) != getattr(rep, f))
        report = ReplayReport(
            replay_id=str(uuid.uuid4()),
            source=src,
            replay=rep,
            versions_match=source_versions == versions,
            changed=changed,
            created_at=self.clock(),
        )
        self.store.record_replay(
            ReplayRecord(
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
        )
        return report
