"""Restricted replay payloads (M3-07 / DEC-013): what a replay or a human reviewer may need beyond the trace
summary — node inputs, the evidence snapshot and the model output — sealed at request time and readable only by an
admin who states a purpose, every read logged. Retention: `retention_days` by default; traces with an escalation
keep their payloads until the escalation is closed plus `escalation_grace_days` (enforced by the purge)."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from medops.api.contracts import TracePayloadItem, TracePayloadResponse
from medops.core.envelope import KeyProvider, Sealed, open_sealed, payload_aad, seal
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext
from medops.harness.runtime import HarnessRun

KINDS = ("input", "evidence_snapshot", "model_output")


class PayloadStore(Protocol):
    def put(self, trace_id: str, node: str, kind: str, sealed: Sealed, expires_at: datetime) -> str: ...

    def list(self, trace_id: str) -> list[dict[str, Any]]: ...

    def log_access(self, principal: str, trace_id: str, purpose: str) -> None: ...

    def purge(self, now: datetime, *, escalation_grace_days: int) -> int: ...


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")


def payloads_from_run(run: HarnessRun, *, query: str) -> dict[str, Mapping[str, Any]]:
    """The three replayable pieces of a harness run (baseline 3.5)."""
    st = run.state
    return {
        "input": {
            "query": query,
            "rewritten_queries": list(st.rewritten_queries),
            "session_entities": [e.model_dump(mode="json") for e in st.session_entities],
            "historical_requested": st.historical_requested,
            "intent": st.intent.model_dump(mode="json") if st.intent else None,
        },
        "evidence_snapshot": {
            "candidates": [c.chunk_id for c in st.candidates],
            "evidence": [
                {
                    "citation": e.citation.model_dump(mode="json"),
                    "text": e.text,
                    "text_hash": e.evidence_text_hash,
                    "status": e.status.value,
                    "historical": e.historical,
                }
                for e in st.evidence
            ],
            "flagged": list(run.flagged_evidence),
        },
        "model_output": {
            "answer": st.answer.model_dump(mode="json") if st.answer else None,
            "escalation": st.escalation.model_dump(mode="json") if st.escalation else None,
            "verify_result": st.verify_result.model_dump(mode="json") if st.verify_result else None,
        },
    }


@dataclass
class PayloadWriter:
    store: PayloadStore
    provider: KeyProvider
    retention_days: int = 90
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))

    def record(self, trace_id: str, node: str, payloads: Mapping[str, Mapping[str, Any]]) -> None:
        expires = self.clock() + timedelta(days=self.retention_days)
        for kind in KINDS:
            if kind not in payloads:
                continue
            sealed = seal(_json_bytes(payloads[kind]), aad=payload_aad(trace_id, node, kind), provider=self.provider)
            self.store.put(trace_id, node, kind, sealed, expires)

    def record_run(self, run: HarnessRun, *, query: str, node: str = "ask") -> None:
        self.record(run.state.trace_id, node, payloads_from_run(run, query=query))


@dataclass
class PayloadReader:
    store: PayloadStore
    provider: KeyProvider

    def read(self, admin: UserContext, trace_id: str, purpose: str) -> TracePayloadResponse:
        rows = self.store.list(trace_id)
        if not rows:
            raise BusinessError(ErrorCode.not_found, "no restricted payload for this trace (never written or purged)")
        self.store.log_access(admin.user_id, trace_id, purpose)  # logged before any plaintext leaves
        items: list[TracePayloadItem] = []
        for r in rows:
            plaintext = open_sealed(
                r["sealed"], aad=payload_aad(trace_id, r["node"], r["kind"]), provider=self.provider
            )
            items.append(
                TracePayloadItem(
                    node=r["node"],
                    kind=r["kind"],
                    created_at=r["created_at"],
                    expires_at=r["expires_at"],
                    kek_version=r["sealed"].kek_version,
                    payload=json.loads(plaintext),
                )
            )
        return TracePayloadResponse(trace_id=trace_id, purpose=purpose, items=tuple(items))


def purge_expired(store: PayloadStore, *, now: datetime | None = None, escalation_grace_days: int = 30) -> int:
    return store.purge(now or datetime.now(UTC), escalation_grace_days=escalation_grace_days)


def snapshot_sizes(payloads: Mapping[str, Mapping[str, Any]]) -> dict[str, int]:
    return {k: len(_json_bytes(v)) for k, v in payloads.items()}


def kinds_present(items: Sequence[TracePayloadItem]) -> tuple[str, ...]:
    return tuple(i.kind for i in items)
