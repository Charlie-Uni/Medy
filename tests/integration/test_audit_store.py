"""PgTraceStore on migration 0011 under the LOGIN users: traces, spans and escalations are written together and
are append-only for the application role; the admin role may only move an escalation's status; feedback binds
to an existing trace with a receipt-bearing idempotency key; the read-only role has no access."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege, RestrictViolation

from medops.application.audit import EscalationRecord, FeedbackRecord, IdempotencyRace, TraceRecord
from medops.domain.common import Dept
from medops.harness.contracts import NodeAttempt
from medops.infrastructure.db.audit import PgTraceStore
from tests.integration.lexical_adapter_suite import make_database

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
PRINCIPAL = "0123456789abcdef" * 2


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


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


def test_trace_spans_escalation_are_appended_and_immutable(db):
    tid = "1" * 32
    esc = EscalationRecord(
        escalation_id=tid,
        trace_id=tid,
        principal=PRINCIPAL,
        dept=Dept.MA,
        reason_codes=("insufficient_evidence",),
        query="q",
        evidence_chunk_ids=("c1",),
        verify_result=None,
        safety_result={"decision": "escalate"},
        policy_version="p1",
        detail="d",
    )
    with psycopg.connect(db["users"]["app"]) as app:
        store = PgTraceStore(app)
        store.record(trace(tid, "escalated"), esc)
        app.commit()
        assert store.trace_principal(tid) == PRINCIPAL and store.trace_principal("2" * 32) is None
        assert app.execute("select count(*) from trace_spans where trace_id = %s", (tid,)).fetchone()[0] == 1
        for sql in (
            "update traces set outcome = 'answered' where trace_id = %s",
            "delete from traces where trace_id = %s",
            "update escalations set status = 'closed' where trace_id = %s",
            "delete from trace_spans where trace_id = %s",
        ):
            with pytest.raises((RestrictViolation, InsufficientPrivilege)):
                app.execute(sql, (tid,))
            app.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute(
            "update escalations set status = 'acknowledged', handled_by = 'reviewer-01', handled_at = now() where trace_id = %s",
            (tid,),
        )
        admin.commit()
        with pytest.raises(RestrictViolation):
            admin.execute("update escalations set detail = 'changed' where trace_id = %s", (tid,))
        admin.rollback()
        with pytest.raises(InsufficientPrivilege):
            admin.execute(
                "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, versions, duration_ms) values ('3333333333333333333333333333333a', '3333333333333333333333333333333a', 'ask', %s, 'MA', 'q', 'answered', '{}', 1)",
                (PRINCIPAL,),
            )
        admin.rollback()


def test_feedback_binds_to_a_trace_with_receipt_idempotency(db):
    tid = "4" * 32
    with psycopg.connect(db["users"]["app"]) as app:
        store = PgTraceStore(app)
        store.record(trace(tid), None)
        app.commit()
        rec = FeedbackRecord(
            feedback_id="00000000-0000-4000-8000-000000000001",
            trace_id=tid,
            principal=PRINCIPAL,
            signal="down",
            correction_text=None,
            created_at=NOW,
        )
        receipt = {"feedback_id": rec.feedback_id, "trace_id": tid}
        store.add_feedback(rec, ("POST /v1/feedback", "k1", "b" * 64, NOW + timedelta(days=1), receipt))
        app.commit()
        assert store.find_receipt(PRINCIPAL, "POST /v1/feedback", "k1") == ("b" * 64, receipt)
        dup = FeedbackRecord(
            feedback_id="00000000-0000-4000-8000-000000000002",
            trace_id=tid,
            principal=PRINCIPAL,
            signal="down",
            correction_text=None,
            created_at=NOW,
        )
        with pytest.raises(IdempotencyRace):
            store.add_feedback(dup, ("POST /v1/feedback", "k1", "b" * 64, NOW + timedelta(days=1), receipt))
        assert (
            app.execute("select count(*) from feedback where trace_id = %s", (tid,)).fetchone()[0] == 1
        )  # savepoint rolled the duplicate back
        app.commit()
        with pytest.raises(Exception):  # noqa: B017 - the check constraint (correction needs text) is what we assert
            store.add_feedback(
                FeedbackRecord(
                    feedback_id="00000000-0000-4000-8000-000000000003",
                    trace_id=tid,
                    principal=PRINCIPAL,
                    signal="correction",
                    correction_text=None,
                    created_at=NOW,
                ),
                None,
            )
        app.rollback()
    with psycopg.connect(db["users"]["readonly"]) as ro:
        for table in ("traces", "trace_spans", "escalations", "feedback"):
            with pytest.raises(InsufficientPrivilege):
                ro.execute(f"select count(*) from {table}")  # noqa: S608 - fixed table names
            ro.rollback()
