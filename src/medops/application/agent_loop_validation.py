"""Validate internal driver results before any tool data enters planning."""

from __future__ import annotations

from datetime import datetime

from medops.application.agent_contracts import context_binding
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_tool_results import (
    AgentToolOutcome,
    ExtractionPayload,
    ReadPayload,
    SearchPayload,
    VerificationPayload,
)
from medops.domain.agent_actions import VerifyCitationsAction
from medops.domain.agent_execution import BoundAction, EvidenceHandle, PVAgentRun
from medops.safety.checks import screen_evidence


def validate_tool_commit(
    action: BoundAction,
    outcome: AgentToolOutcome,
    run: PVAgentRun,
    registry: tuple[EvidenceHandle, ...],
    *,
    now: datetime,
) -> tuple[AgentToolOutcome, tuple[EvidenceHandle, ...]]:
    outcome = AgentToolOutcome.model_validate(outcome.model_dump(mode="python", warnings=False))
    if outcome.action_id != action.action_id or outcome.binding != context_binding(run.context):
        raise AgentLoopAbort("audit_failure")
    payload = outcome.payload
    if payload is not None and payload.action != action.proposal.action:
        raise AgentLoopAbort("audit_failure")
    # Never accept a reissued/changed UUID as a new fact. Reuse is not progress.
    merged = {h.handle: h for h in registry}
    allowed = {(s.doc_id, s.version, s.source_sha256) for s in run.context.source_scope.allowed_sources}
    for item in outcome.issued_handles:
        item = EvidenceHandle.model_validate(item.model_dump(mode="python", warnings=False))
        c = item.evidence.citation
        if (
            item.handle in merged
            or item.binding != action.binding
            or not now < item.expires_at <= run.expires_at
            or (c.doc_id, c.version, item.source_sha256) not in allowed
            or c.effective_date > run.context.query_context.as_of
            or item.evidence.historical
            and not run.context.query_context.historical_requested
        ):
            raise AgentLoopAbort("audit_failure")
        kept, _ = screen_evidence((item.evidence,))
        if not kept:
            raise AgentLoopAbort("safety_boundary")
        merged[item.handle] = item
    if len(merged) > 64:
        raise AgentLoopAbort("unsupported_requirement")
    if isinstance(payload, SearchPayload) and (
        outcome.kind == "empty" and payload.matches or outcome.kind == "ok" and not payload.matches
    ):
        raise AgentLoopAbort("audit_failure")
    if outcome.kind != "ok":
        return outcome, registry  # no failed payload enters planning
    if isinstance(payload, (SearchPayload, ReadPayload)):
        views = payload.matches if isinstance(payload, SearchPayload) else (payload.evidence,)
        if not {h.handle for h in outcome.issued_handles} <= {v.handle for v in views}:
            raise AgentLoopAbort("audit_failure")
        for view in views:
            record = merged.get(view.handle)
            if record is None:
                raise AgentLoopAbort("audit_failure")
            evidence = record.evidence
            if (
                view.citation != evidence.citation
                or view.evidence_text_sha256 != evidence.evidence_text_hash
                or view.source_sha256 != record.source_sha256
                or view.text != evidence.text[: len(view.text)]
                or view.truncated != (len(view.text) < len(evidence.text))
            ):
                raise AgentLoopAbort("audit_failure")
    elif isinstance(payload, ExtractionPayload):
        if outcome.issued_handles or not payload.elements or payload.unaligned_elements:
            raise AgentLoopAbort("audit_failure")
        for element in payload.elements:
            if run.context.narrative[element.char_start : element.char_end] != element.quote:
                raise AgentLoopAbort("audit_failure")
    elif isinstance(payload, VerificationPayload):
        if outcome.issued_handles or not isinstance(action.proposal, VerifyCitationsAction):
            raise AgentLoopAbort("audit_failure")
        wanted = {(c.requirement_id, c.text, frozenset(c.evidence_handles)) for c in action.proposal.claims}
        actual = {(c.requirement_id, c.text, frozenset(c.requested_handles)) for c in payload.checks}
        if wanted != actual or len(payload.checks) != len(wanted):
            raise AgentLoopAbort("audit_failure")
    else:
        raise AgentLoopAbort("audit_failure")
    return outcome, tuple(merged.values())
