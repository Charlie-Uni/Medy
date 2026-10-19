"""Body-free business Trace projection of a trusted, committed Agent terminal.

The caller must write this on the terminal's transaction. This is neither an
execution journal nor a reconstruction of OpenTelemetry/Harness spans.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from medops.application.agent_terminal import TerminalEnvelope, TerminalStatus
from medops.application.audit import TraceRecord
from medops.domain.agent_actions import AgentModel
from medops.domain.agent_execution import AgentVersions, StopReason
from medops.domain.common import Sha256

Count = Annotated[int, Field(ge=0, strict=True)]
Amount = Annotated[float, Field(ge=0, strict=True)]


class AgentTraceAccounting(AgentModel):
    """Explicit numeric allowlist; generic checkpoints can contain free text."""

    token_limit: Count
    cost_limit_usd: Amount
    timeout_s: Amount
    accounted_tokens: Count
    known_tokens: Count
    reserved_tokens: Count
    accounted_cost_usd: Amount
    known_cost_usd: Amount
    reserved_cost_usd: Amount
    calls: Count
    protected_tokens: Count
    protected_cost_usd: Amount
    blocked: Annotated[bool, Field(strict=True)]


class AgentTraceMetadata(AgentModel):
    schema_version: Literal["pv-agent-trace-v1"] = "pv-agent-trace-v1"
    case_id: UUID
    task_id: UUID
    run_id: UUID
    attempt_id: UUID
    context_sha256: Sha256
    terminal_event_id: UUID
    terminal_material_ref: UUID
    terminal_material_sha256: Sha256
    versions: AgentVersions
    status: TerminalStatus
    reason: StopReason
    decisions_consumed: Annotated[int, Field(ge=0, le=8, strict=True)]
    budget_checkpoint_id: UUID
    accounting: AgentTraceAccounting
    accounting_complete: Annotated[bool, Field(strict=True)]
    pending_calls: Annotated[int, Field(ge=0, strict=True)]
    started_at: datetime
    stopped_at: datetime


def terminal_trace(envelope: TerminalEnvelope, *, event_id: UUID) -> TraceRecord:
    """Project explicit identifiers/counters only; never copy narrative or model text."""
    run, material = envelope.delivery.run, envelope.delivery.material
    context, terminal = run.context, run.terminal
    if terminal is None or run.stopped_at is None:
        raise ValueError("missing_agent_terminal")
    duration_ms = (run.stopped_at - run.started_at).total_seconds() * 1000
    if duration_ms < 0:
        raise ValueError("invalid_agent_trace_duration")
    snapshot = envelope.budget.snapshot
    identity = context.identity
    metadata = AgentTraceMetadata(
        case_id=identity.case_id,
        task_id=identity.task_id,
        run_id=identity.run_id,
        attempt_id=identity.attempt_id,
        context_sha256=terminal.binding.conditions_sha256,
        terminal_event_id=event_id,
        terminal_material_ref=terminal.material_ref,
        terminal_material_sha256=terminal.material_sha256,
        versions=context.versions,
        status=material.status,
        reason=material.reason,
        decisions_consumed=run.decisions_consumed,
        budget_checkpoint_id=envelope.budget.checkpoint_id,
        accounting=AgentTraceAccounting(
            token_limit=snapshot.limits.token_limit,
            cost_limit_usd=snapshot.limits.cost_limit_usd,
            timeout_s=snapshot.limits.timeout_s,
            accounted_tokens=snapshot.accounted_tokens,
            known_tokens=snapshot.known_tokens,
            reserved_tokens=snapshot.reserved_tokens,
            accounted_cost_usd=snapshot.accounted_cost_usd,
            known_cost_usd=snapshot.known_cost_usd,
            reserved_cost_usd=snapshot.reserved_cost_usd,
            calls=snapshot.calls,
            protected_tokens=snapshot.protected_tokens,
            protected_cost_usd=snapshot.protected_cost_usd,
            blocked=snapshot.blocked_reason is not None,
        ),
        accounting_complete=envelope.accounted_complete,
        pending_calls=len(envelope.budget.pending),
        started_at=run.started_at,
        stopped_at=run.stopped_at,
    )
    evidence = tuple(dict.fromkeys(h.evidence.citation.chunk_id for h in envelope.registry))
    cited: tuple[str, ...] = ()
    if material.review is not None:
        handles = {h for c in material.review.guideline_claims for group in c.support_groups for h in group}
        if not handles <= {h.handle for h in material.review.evidence}:
            raise ValueError("invalid_agent_trace_citations")
        cited = tuple(dict.fromkeys(e.citation.chunk_id for e in material.review.evidence if e.handle in handles))
        if not set(cited) <= set(evidence):
            raise ValueError("invalid_agent_trace_citations")
    return TraceRecord(
        trace_id=identity.trace_id,
        run_id=identity.run_id.hex,
        kind="agent",
        principal=context.principal.user_id,
        dept=context.principal.dept,
        query="",  # PV narrative and requirement/source descriptions stay encrypted.
        outcome=material.status,
        reason_codes=(material.reason,),
        versions=context.versions.versions.model_dump(mode="json"),
        evidence_chunk_ids=evidence,
        cited_chunk_ids=cited,
        flagged_chunk_ids=(),
        model_calls=snapshot.calls,
        tokens=snapshot.accounted_tokens,
        cost_usd=snapshot.accounted_cost_usd,
        duration_ms=duration_ms,  # Original business wall time, including any recovery gap.
        spans=(),  # Actual Agent actions are in its journal, not fabricated Harness attempts.
        task_id=str(identity.task_id),
        query_context=context.query_context,
        agent_metadata=metadata.model_dump(mode="json"),
    )
