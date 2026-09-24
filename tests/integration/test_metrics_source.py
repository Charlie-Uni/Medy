"""PgMetricsSource on migration 0011 tables: windowed counts, quantiles, spend, escalation and task gauges."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from medops.api.contracts import TaskStatus
from medops.application.audit import EscalationRecord, TraceRecord
from medops.application.metrics import PgMetricsSource
from medops.application.tasks import TaskRecord
from medops.domain.common import Dept
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.tasks import PgTaskStore
from tests.integration.lexical_adapter_suite import make_database

NOW = datetime.now(UTC)  # traces get created_at = now() in the database, so the window must use the real clock
P = "0123456789abcdef" * 2


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


def trace(tid: str, outcome: str, ms: float, cost: float, created: datetime) -> TraceRecord:
    return TraceRecord(
        trace_id=tid,
        run_id=tid,
        kind="ask",
        principal=P,
        dept=Dept.MA,
        query="q",
        outcome=outcome,
        reason_codes=("insufficient_evidence",) if outcome == "escalated" else (),
        versions={},
        evidence_chunk_ids=(),
        cited_chunk_ids=(),
        flagged_chunk_ids=(),
        model_calls=2,
        tokens=100,
        cost_usd=cost,
        duration_ms=ms,
        spans=(),
    )


def test_snapshot_aggregates_window_month_escalations_and_tasks(db):
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTraceStore(conn)
        store.record(trace("a" * 32, "answered", 1000, 0.01, NOW), None)
        store.record(trace("b" * 32, "answered", 3000, 0.02, NOW), None)
        esc = EscalationRecord(
            escalation_id="c" * 32,
            trace_id="c" * 32,
            principal=P,
            dept=Dept.MA,
            reason_codes=("insufficient_evidence",),
            query="q",
            evidence_chunk_ids=(),
            verify_result=None,
            safety_result=None,
            policy_version="p",
            detail="",
        )
        store.record(trace("c" * 32, "escalated", 5000, 0.03, NOW), esc)
        conn.execute(
            "update traces set created_at = %s where trace_id = %s", (NOW - timedelta(hours=3), "a" * 32)
        ) if False else None
        tasks = PgTaskStore(conn)
        tasks.create(
            TaskRecord(
                task_id="00000000-0000-4000-8000-00000000000a",
                principal=P,
                dept=Dept.MA,
                skill_name="echo_skill",
                skill_version="1.0.0",
                input={},
                status=TaskStatus.queued,
                created_at=NOW - timedelta(seconds=90),
                updated_at=NOW,
            ),
            None,
        )
        conn.commit()
        snap = PgMetricsSource(conn).snapshot(window_minutes=60, now=NOW + timedelta(minutes=1))
        assert snap.requests[("ask", "answered")] == 2 and snap.requests[("ask", "escalated")] == 1
        assert snap.escalations == {"insufficient_evidence": 1} and snap.open_escalations == 1
        assert (
            snap.duration_ms_quantiles[("ask", "0.5")] == 3000.0 and snap.duration_ms_quantiles[("ask", "0.95")] > 4000
        )
        assert snap.model_calls == 6 and snap.tokens == 300 and abs(snap.cost_usd_window - 0.06) < 1e-6
        assert abs(snap.cost_usd_month - 0.06) < 1e-6
        assert snap.tasks_by_status == {"queued": 1} and 89 <= snap.oldest_queued_age_s <= 151
        later = PgMetricsSource(conn).snapshot(window_minutes=60, now=NOW + timedelta(hours=2))
        assert later.requests == {}  # outside the 60-minute window
        if (NOW + timedelta(hours=2)).month == NOW.month:
            assert abs(later.cost_usd_month - 0.06) < 1e-6  # still inside the month
