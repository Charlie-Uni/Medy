"""Private, body-free Agent diagnostic reports from authenticated saved material.

No execution, authorization or historical environment restoration happens here.
Old loop checkpoints are deliberately not decoded as today's executable state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid5

from pydantic import Field

from medops.application.agent_planning import PlannerConfig
from medops.application.agent_runtime_state import DurableCall, owned_request, verify_accounting
from medops.application.agent_terminal import TerminalEnvelope
from medops.application.agent_trace import AgentTraceMetadata, terminal_trace
from medops.application.audit import TraceSummary
from medops.application.contracts import ReplayConditions, TracePayloadResponse
from medops.core.canonical import canonical_hash, sha256_hex
from medops.domain.agent_actions import ActionName, AgentModel
from medops.domain.agent_execution import AgentContext, AgentIdentity, ObservationKind
from medops.domain.common import Sha256


class AgentReplayRequest(AgentModel):
    # Keep this UUID on retries. A new UUID requests a NEW potentially paid run.
    replay_id: UUID
    reason: Annotated[str, Field(min_length=8, max_length=500, pattern=r"\S")]
    mode: Literal["diagnostic_current", "original_conditions"] = "diagnostic_current"


class AgentReplaySide(AgentModel):
    trace_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
    metadata: AgentTraceMetadata
    input_sha256: Sha256
    source_scope_sha256: Sha256
    evidence_sha256: Sha256
    output_sha256: Sha256
    cited_chunk_ids: tuple[str, ...]
    evidence_chunk_ids: tuple[str, ...]
    actions: tuple[tuple[ActionName, ObservationKind], ...]
    actual_models_sha256: Sha256 | None


class AgentReplayReport(AgentModel):
    schema_version: Literal["pv-agent-replay-v1"] = "pv-agent-replay-v1"
    replay_id: UUID
    source: AgentReplaySide
    replay: AgentReplaySide
    mode: Literal["diagnostic_current"] = "diagnostic_current"
    versions_match: bool  # Base version labels only, like the existing Ask report.
    conditions: ReplayConditions
    source_scope_match: bool
    profile_match: bool
    changed: tuple[str, ...]
    created_at: datetime


def replay_identity(replay_id: UUID) -> AgentIdentity:
    """All five identities are fresh and stable for this explicit diagnostic command."""
    return AgentIdentity(
        **{
            name: uuid5(replay_id, "medy-agent-diagnostic/" + name)
            for name in ("case_id", "task_id", "run_id", "attempt_id")
        },
        trace_id=uuid5(replay_id, "medy-agent-diagnostic/trace_id").hex,
    )


def input_digest(context: AgentContext) -> str:
    return canonical_hash(
        {
            "narrative": context.narrative,
            "synthetic": context.synthetic,
            "source_type": context.source_type,
            "requirements": [r.model_dump(mode="json") for r in context.requirements],
            "clarifiable_fields": context.clarifiable_fields,
            "query_context": context.query_context.model_dump(mode="json"),
            "requested_document": context.source_scope.requested_document,
            "requested_version": context.source_scope.requested_version,
        }
    )


@dataclass(frozen=True)
class AgentReplaySnapshot:
    envelope: TerminalEnvelope
    config: PlannerConfig
    calls: tuple[DurableCall, ...]
    metadata: AgentTraceMetadata
    # Private audit material, not included in the report/telemetry.
    provenance: tuple[dict, ...]

    @property
    def context(self) -> AgentContext:
        return self.envelope.delivery.run.context

    def side(self) -> AgentReplaySide:
        context = self.context
        material = self.envelope.delivery.material
        trace = terminal_trace(self.envelope, event_id=self.metadata.terminal_event_id)
        evidence = {
            str(h.handle): {
                "citation": h.evidence.citation.model_dump(mode="json"),
                "source_sha256": h.source_sha256,
                "text_sha256": sha256_hex(h.evidence.text),
            }
            for h in self.envelope.registry
        }
        output = material.model_dump(
            mode="json",
            exclude={"binding", "call_receipt_ids", "pending_call_ids", "committed_actions", "review", "escalation"},
        )
        if material.review is not None:
            review = material.review
            output["review"] = {
                "gates": review.gates.model_dump(mode="json"),
                "narrative_facts": [f.model_dump(mode="json") for f in review.narrative_facts],
                "claims": [
                    {
                        "requirement_id": c.requirement_id,
                        "text": c.text,
                        "support_groups": sorted(
                            sorted(canonical_hash(evidence[str(h)]) for h in group) for group in c.support_groups
                        ),
                    }
                    for c in review.guideline_claims
                ],
            }
        models = None
        if all(
            c.receipt is not None and (not c.receipt.provider_started or c.response is not None) for c in self.calls
        ):
            models = canonical_hash(
                [
                    [
                        c.request.purpose,
                        c.request.model_id,
                        c.response.provider if c.response else None,
                        c.response.model_id if c.response else None,
                        c.response.system_fingerprint if c.response else None,
                    ]
                    for c in self.calls
                ]
            )
        return AgentReplaySide(
            trace_id=trace.trace_id,
            metadata=self.metadata,
            input_sha256=input_digest(context),
            source_scope_sha256=canonical_hash(context.source_scope.model_dump(mode="json")),
            evidence_sha256=canonical_hash(sorted(canonical_hash(e) for e in evidence.values())),
            output_sha256=canonical_hash(output),
            cited_chunk_ids=tuple(sorted(trace.cited_chunk_ids)),
            evidence_chunk_ids=tuple(sorted(trace.evidence_chunk_ids)),
            actions=tuple((a.action, a.outcome) for a in material.committed_actions),
            actual_models_sha256=models,
        )


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("invalid_agent_replay_object")
    return value


def saved_agent_snapshot(payload: TracePayloadResponse, trace: TraceSummary, metadata: dict) -> AgentReplaySnapshot:
    """Strictly validate a supported terminal source; never infer a missing input."""
    if not payload.items or payload.trace_id != trace.trace_id or trace.kind != "agent":
        raise ValueError("invalid_agent_replay_source")
    head, *events = payload.items
    head_payload = _object(head.payload)
    head_body = _object(head_payload["body"])
    control = _object(head_payload["control"])
    context = AgentContext.model_validate(_object(head_body["run"])["context"])
    records = [(e, _object(e.payload), _object(_object(e.payload)["body"])) for e in events]
    selected = [(e, p, b) for e, p, b in records if p["event_id"] == control["terminal_ref"]]
    if len(selected) != 1:
        raise ValueError("agent_replay_requires_saved_business_terminal")
    event, data, body = selected[0]
    if event.kind != "late_stop" or body.get("kind") != "business_terminal":
        raise ValueError("agent_replay_requires_saved_business_terminal")
    envelope = TerminalEnvelope.model_validate(body["envelope"])
    expected = terminal_trace(envelope, event_id=UUID(data["event_id"]))
    parsed = AgentTraceMetadata.model_validate(metadata)
    if (
        envelope.delivery.run.context != context
        or envelope.delivery.run.status != control["terminal_status"]
        or parsed.model_dump(mode="json") != expected.agent_metadata
        or any(
            getattr(trace, n) != getattr(expected, n)
            for n in (
                "trace_id",
                "run_id",
                "principal",
                "dept",
                "query",
                "outcome",
                "reason_codes",
                "versions",
                "evidence_chunk_ids",
                "cited_chunk_ids",
                "query_context",
            )
        )
    ):
        raise ValueError("agent_replay_source_binding_mismatch")
    starts = {p["item_id"]: b for e, p, b in records if e.kind == "call_admitted"}
    ends = {p["item_id"]: b for e, p, b in records if e.kind == "call_settled"}
    if len(starts) != sum(e.kind == "call_admitted" for e in events) or not ends.keys() <= starts.keys():
        raise ValueError("invalid_agent_replay_calls")
    calls = []
    for call_id, first in starts.items():
        a = DurableCall.model_validate(first)
        b = DurableCall.model_validate(ends[call_id]) if call_id in ends else a
        owned_request(b.request, context)
        if (
            str(b.allowance.call_id) != call_id
            or b.request != a.request
            or b.allowance != a.allowance
            or (call_id in ends and b.receipt is None)
        ):
            raise ValueError("invalid_agent_replay_calls")
        calls.append(b)
    if {str(c.allowance.call_id) for c in calls if c.receipt is not None} != set(
        envelope.delivery.material.call_receipt_ids
    ) or {str(c.allowance.call_id) for c in calls if c.receipt is None} != set(
        envelope.delivery.material.pending_call_ids
    ):
        raise ValueError("invalid_agent_replay_accounting")
    verify_accounting(envelope.budget, tuple(calls), context)
    return AgentReplaySnapshot(
        envelope,
        PlannerConfig.model_validate(head_body["config"]),
        tuple(calls),
        parsed,
        tuple(b for e, p, b in records if e.kind == "checkpoint" and b.get("kind") == "diagnostic_replay"),
    )


def agent_replay_report(replay_id: UUID, source: AgentReplaySnapshot, replay: AgentReplaySnapshot) -> AgentReplayReport:
    a, b = source.side(), replay.side()
    profile_match = source.context.profile == replay.context.profile
    versions_match = source.context.versions.versions == replay.context.versions.versions
    fields = ("cited_chunk_ids", "evidence_chunk_ids", "evidence_sha256", "output_sha256", "actions")
    changed = tuple(
        n for n in ("status", "reason", "decisions_consumed") if getattr(a.metadata, n) != getattr(b.metadata, n)
    )
    changed += tuple(n for n in fields if getattr(a, n) != getattr(b, n))
    return AgentReplayReport(
        replay_id=replay_id,
        source=a,
        replay=b,
        versions_match=versions_match,
        source_scope_match=a.source_scope_sha256 == b.source_scope_sha256,
        profile_match=profile_match,
        conditions=ReplayConditions(
            input_complete=True,
            input_match=a.input_sha256 == b.input_sha256,
            identity_match=source.context.principal == replay.context.principal,
            configuration_match=source.config == replay.config and profile_match,
            routed_policy_match=source.context.versions.fact_conditions_sha256
            == replay.context.versions.fact_conditions_sha256,
            evidence_match=a.evidence_sha256 == b.evidence_sha256,
            actual_models_match=a.actual_models_sha256 == b.actual_models_sha256
            if a.actual_models_sha256 is not None and b.actual_models_sha256 is not None
            else None,
            limitations=(
                "current_permissions_facts_and_policies",
                "fresh_independent_diagnostic_execution",
                "corpus_and_index_snapshot_not_restored",
                "attested_loaded_build_unavailable",
                "rendered_model_messages_not_compared",
                "provider_weights_and_nondeterminism_unpinned",
                "differences_are_not_causal_attribution",
            ),
        ),
        changed=changed,
        created_at=b.metadata.stopped_at,
    )
