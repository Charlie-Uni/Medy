"""Shared transactional audit persistence for Ask and asynchronous Skills.

Callers own the transaction. Public results are released only after trace and any
configured encrypted payloads commit. This service never retries business execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from medops.application.audit import EscalationRecord, TraceRecord, TraceStore, record_or_fail_closed
from medops.application.payloads import PayloadWriter
from medops.core.errors import ErrorCode, InfrastructureError
from medops.core.telemetry import run_metadata, span
from medops.domain.common import DomainModel
from medops.domain.evidence import Citation
from medops.harness.audit import ExecutionAuditSnapshot
from medops.harness.contracts import NodeAttempt


@dataclass
class ExecutionAuditWriter:
    traces: TraceStore
    payloads: PayloadWriter | None

    def record(
        self,
        trace: TraceRecord,
        escalation: EscalationRecord | None,
        *,
        node: str,
        payloads: Mapping[str, Mapping[str, Any]],
    ) -> None:
        try:
            with (
                run_metadata(trace.trace_id, trace.versions, kind=trace.kind),
                span("audit.persist", restricted_payload_enabled=self.payloads is not None),
            ):
                record_or_fail_closed(self.traces, trace, escalation)
                if self.payloads is not None:
                    self.payloads.record(trace.trace_id, node, payloads)
        except Exception as exc:  # noqa: BLE001 - seal/store failures cannot release unaudited results
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__, retryable=True) from None


def output_citations(output: DomainModel, audit: ExecutionAuditSnapshot) -> tuple[str, ...]:
    observed = {e.citation.chunk_id: e.citation for e in audit.evidence}
    cited: dict[str, None] = {}

    def walk(value: Any) -> None:
        if isinstance(value, Citation):
            if observed.get(value.chunk_id) != value:
                raise InfrastructureError(
                    ErrorCode.audit_unavailable, detail="output citation lacks matching observed evidence"
                )
            cited[value.chunk_id] = None
        elif isinstance(value, DomainModel):
            for key in type(value).model_fields:
                walk(getattr(value, key))
        elif isinstance(value, (tuple, list)):
            for item in value:
                walk(item)

    walk(output)
    return tuple(cited)


def task_spans(audit: ExecutionAuditSnapshot) -> tuple[NodeAttempt, ...]:
    # DB uniqueness is (trace,node,attempt); inner invocations/retries can reuse local ordinals.
    # Keep those original ordinals/keys in encrypted events, assign trace-local ordinals here.
    counts: dict[str, int] = {}
    spans: list[NodeAttempt] = []
    for item in sorted(audit.spans, key=lambda s: s.started_at):
        counts[item.node] = counts.get(item.node, 0) + 1
        spans.append(item.model_copy(update={"attempt": counts[item.node], "detail": ""}))
    return tuple(spans)


def task_payloads(
    *,
    raw_input: Mapping[str, Any],
    skill: str,
    query_context: Mapping[str, Any] | None,
    versions: Mapping[str, Any],
    audit: ExecutionAuditSnapshot,
    output: DomainModel | None,
    error: Mapping[str, Any] | None,
    safety: Mapping[str, Any] | None,
    attempt: int,
    outcome: str,
    model_calls: Sequence[Mapping[str, Any]] = (),
    historical: Mapping[str, Any] | None = None,
    conditions: Mapping[str, Any] | None = None,
    model_call_audit_complete: bool = True,
    call_receipts: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Mapping[str, Any]]:
    return {
        "input": {
            "format_version": "task-audit-v1",
            "skill": skill,
            "input": dict(raw_input),
            "query_context": query_context,
            "versions": dict(versions),
            "attempt": attempt,
            "historical": dict(historical) if historical is not None else None,
            "conditions": next(
                (e["conditions"] for e in audit.events if e["kind"] == "skill_execution_input"),
                dict(conditions) if conditions is not None else None,
            ),
            "execution_inputs": [e for e in audit.events if e["kind"] == "skill_execution_input"],
            "harness_inputs": [e["payloads"]["input"] for e in audit.events if e["kind"] == "harness"],
        },
        "evidence_snapshot": {
            "format_version": "task-audit-v1",
            "evidence": [e.model_dump(mode="json") for e in audit.evidence],
            "flagged": list(audit.flagged),
            "harness_snapshots": [e["payloads"]["evidence_snapshot"] for e in audit.events if e["kind"] == "harness"],
            "rendered_evidence": [e for e in audit.events if e["kind"] == "rendered_evidence"],
            "retrieval_events": [e for e in audit.events if e["kind"] == "retrieval"],
        },
        "model_output": {
            "format_version": "task-audit-v1",
            "output": output.model_dump(mode="json") if output else None,
            "error": dict(error) if error else None,
            "safety_result": dict(safety) if safety else None,
            "attempt_outcome": outcome,
            "events": list(audit.events),
            "model_calls": list(model_calls),
            "model_call_audit_complete": model_call_audit_complete,
            "call_receipts": list(call_receipts),
        },
    }
