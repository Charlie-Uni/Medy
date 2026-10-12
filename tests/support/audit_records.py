"""Shared audit records test support; no collected test cases."""

from __future__ import annotations

from datetime import UTC, datetime

from medops.application.audit import TraceRecord
from medops.domain.common import Dept
from medops.harness.contracts import NodeAttempt

NOW = datetime(
    2026, 9, 23, 12, 0, tzinfo=UTC
)  # fixed for stored timestamps; idempotency expiry is relative to the DB clock (expires_at > now())


PRINCIPAL = "0123456789abcdef" * 2


def trace(trace_id: str, outcome: str = "answered") -> TraceRecord:
    return TraceRecord(
        trace_id=trace_id,
        run_id=trace_id,
        kind="ask",
        principal=PRINCIPAL,
        dept=Dept.MA,
        query="q",
        outcome=outcome,
        reason_codes=("insufficient_evidence",) if outcome == "escalated" else (),
        versions={"policy_version": "p1"},
        evidence_chunk_ids=("c1",),
        cited_chunk_ids=("c1",) if outcome == "answered" else (),
        flagged_chunk_ids=(),
        model_calls=2,
        tokens=100,
        cost_usd=0.0123,
        duration_ms=12.5,
        spans=(
            NodeAttempt(
                node="intent", attempt=1, operation_key="a" * 64, started_at=NOW, duration_ms=1.0, outcome="ok"
            ),
        ),
    )
