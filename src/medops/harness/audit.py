"""Bounded, request-local execution facts. Bodies are for encrypted storage only.

This journal never writes telemetry, calls a provider, or changes retry/deadline policy.
One registry execution owns one journal; parallel children must have separate journals.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from medops.core.canonical import canonical_hash
from medops.core.errors import ErrorCode, InfrastructureError, MedOpsError
from medops.domain.evidence import Evidence
from medops.harness.contracts import NodeAttempt

if TYPE_CHECKING:
    from medops.harness.runtime import HarnessRun

MAX_AUDIT_EVENTS = 512
MAX_AUDIT_BYTES = 16 * 1024 * 1024


def audit_step(
    journal: ExecutionAudit | None, node: str, inputs: Mapping[str, Any]
) -> AbstractContextManager[dict[str, Any]]:
    return journal.step(node, inputs) if journal is not None else nullcontext({"output": None})


def run_payloads(run: HarnessRun, *, query: str) -> dict[str, Mapping[str, Any]]:
    st = run.state
    manifest = [
        {
            "citation": e.citation.model_dump(mode="json"),
            "status": e.status.value,
            "historical": e.historical,
            "evidence_text_hash": e.evidence_text_hash,
            "chunk_content_hash": e.chunk_content_hash,
        }
        for e in st.evidence
    ]
    return {
        "input": {
            "format_version": "ask-audit-v2",
            "execution_input": dict(run.execution_input),
            "conditions": dict(run.conditions),
            "query": query,
            "rewritten_queries": list(st.rewritten_queries),
            "session_entities": [e.model_dump(mode="json") for e in st.session_entities],
            "historical_requested": st.historical_requested,
            "query_context": st.query_context.model_dump(mode="json") if st.query_context else None,
            "intent": st.intent.model_dump(mode="json") if st.intent else None,
        },
        "evidence_snapshot": {
            "candidates": [c.chunk_id for c in st.candidates],
            "candidate_details": [c.model_dump(mode="json") for c in st.candidates],
            "observed_fact_manifest": manifest,
            "observed_fact_manifest_sha256": canonical_hash(manifest),
            "evidence": [e.model_dump(mode="json") | {"text_hash": e.evidence_text_hash} for e in st.evidence],
            "flagged": list(run.flagged_evidence),
        },
        "model_output": {
            "model_calls": list(run.model_calls),
            "model_call_audit_complete": True,
            "answer": st.answer.model_dump(mode="json") if st.answer else None,
            "escalation": st.escalation.model_dump(mode="json") if st.escalation else None,
            "verify_result": st.verify_result.model_dump(mode="json") if st.verify_result else None,
            "safety_result": st.safety_result.model_dump(mode="json") if st.safety_result else None,
        },
    }


@dataclass(frozen=True)
class ExecutionAuditSnapshot:
    evidence: tuple[Evidence, ...]
    flagged: tuple[str, ...]
    spans: tuple[NodeAttempt, ...]
    events: tuple[Mapping[str, Any], ...]


class ExecutionAudit:
    def __init__(self, *, max_events: int = MAX_AUDIT_EVENTS, max_bytes: int = MAX_AUDIT_BYTES) -> None:
        self._max_events, self._max_bytes = max_events, max_bytes
        self._bytes = 0
        self._events: list[Mapping[str, Any]] = []
        self._spans: list[NodeAttempt] = []
        self._evidence: dict[str, Evidence] = {}
        self._flagged: dict[str, None] = {}
        self._steps = 0
        self._blocked = False
        self._owner: tuple[str, str] | None = None

    def bind(self, trace_id: str, principal: str) -> None:
        if self._owner is not None:
            raise InfrastructureError(ErrorCode.audit_unavailable, detail="execution journal cannot be reused")
        self._owner = (trace_id, principal)

    def check_owner(self, trace_id: str, principal: str) -> None:
        if self._owner is not None and self._owner != (trace_id, principal):
            raise InfrastructureError(ErrorCode.audit_unavailable, detail="harness audit identity disagrees")

    def _ensure(self) -> None:
        if self._blocked:
            raise InfrastructureError(ErrorCode.audit_unavailable, detail="execution audit capacity exceeded")

    def _append(self, event: Mapping[str, Any]) -> None:
        self._ensure()
        encoded = json.dumps(event, ensure_ascii=False, default=str).encode("utf-8")
        if len(self._events) >= self._max_events or self._bytes + len(encoded) > self._max_bytes:
            self._blocked = True
            self._ensure()
        self._events.append(json.loads(encoded))  # no mutable references to the caller's bodies
        self._bytes += len(encoded)

    def observe(self, evidence: Sequence[Evidence], flagged: Sequence[str] = ()) -> None:
        self._append(
            {"kind": "evidence", "evidence": [e.model_dump(mode="json") for e in evidence], "flagged": list(flagged)}
        )
        for e in evidence:
            prior = self._evidence.get(e.citation.chunk_id)
            if prior is not None and prior != e:
                self._blocked = True
                raise InfrastructureError(ErrorCode.audit_unavailable, detail="conflicting evidence snapshots")
            self._evidence[e.citation.chunk_id] = e
        self._flagged.update(dict.fromkeys(flagged))

    def record_run(self, run: HarnessRun) -> None:
        self.observe(run.state.evidence, run.flagged_evidence)
        self._append({"kind": "harness", "payloads": run_payloads(run, query=run.state.query)})

    def record_event(self, kind: str, payload: Mapping[str, Any]) -> None:
        self._append({"kind": kind, **dict(payload)})

    def record_attempts(self, attempts: Sequence[NodeAttempt]) -> None:
        self._append({"kind": "attempts", "attempts": [a.model_dump(mode="json") for a in attempts]})
        self._spans.extend(attempts)

    @contextmanager
    def step(self, node: str, inputs: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        self._ensure()
        self._steps += 1
        key = canonical_hash({"node": node, "ordinal": self._steps, "input": inputs})
        started_at, started = datetime.now(UTC), time.perf_counter()
        event: dict[str, Any] = {"kind": "step", "node": node, "input": inputs, "output": None}
        error: BaseException | None = None
        try:
            yield event
        except BaseException as exc:
            error = exc
            raise
        finally:
            code = error.code.value if isinstance(error, MedOpsError) else ("internal_error" if error else None)
            event["error_type"] = type(error).__name__ if error else None
            self._append(event)
            self._spans.append(
                NodeAttempt(
                    node=node,
                    attempt=1,
                    operation_key=key,
                    started_at=started_at,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    outcome=("timeout" if code == ErrorCode.dependency_timeout.value else "failed") if error else "ok",
                    error_code=code,
                )
            )

    def snapshot(self) -> ExecutionAuditSnapshot:
        # Even when capacity failed, retain the bounded prefix for failure diagnostics.
        return ExecutionAuditSnapshot(
            tuple(self._evidence.values()),
            tuple(self._flagged),
            tuple(self._spans),
            tuple(json.loads(json.dumps(self._events))),
        )

    def ensure_complete(self) -> None:
        self._ensure()
