"""Read-only audit collection, late commits and durable cursor recovery on a disposable DB."""

from datetime import UTC, datetime

import psycopg
import pytest

from medops.application.audit import FeedbackRecord
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.observability import ScoreQueue, harvest_feedback
from tests.integration.test_audit_store import db as db  # noqa: F401
from tests.integration.test_audit_store import trace


def insert_feedback(db, feedback_id, trace_id):
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTraceStore(conn)
        store.record(trace(trace_id), None)
        store.add_feedback(
            FeedbackRecord(
                feedback_id, trace_id, "p", "correction", "PRIVATE_CORRECTION", datetime(2026, 10, 8, tzinfo=UTC)
            ),
            None,
        )
        conn.commit()


def collect(db, queue, **kwargs):
    with psycopg.connect(db["owner"]) as conn:
        conn.read_only = True
        return harvest_feedback(conn, queue, **kwargs)


def test_committed_feedback_and_late_lower_id_found_after_sweep(db, tmp_path):
    insert_feedback(db, "ffffffff-ffff-4fff-bfff-fffffffffff1", "e" * 32)
    path = tmp_path / "queue.db"
    q = ScoreQueue(path, "fixture")
    assert collect(db, q, limit=1)["enqueued"] == 1
    q.close()
    # Commit a lower UUID after the scan cursor has advanced: a timestamp-only incremental scan can miss this.
    insert_feedback(db, "11111111-1111-4111-8111-111111111111", "f" * 32)
    q = ScoreQueue(path, "fixture")
    assert collect(db, q, limit=1)["sweep_complete"]
    assert collect(db, q, limit=1)["enqueued"] == 1
    assert collect(db, q, limit=1)["enqueued"] == 0
    assert collect(db, q, limit=1)["sweep_complete"]
    payloads = q.conn.execute("select payload from scores").fetchall()
    assert len(payloads) == 2 and "PRIVATE_CORRECTION" not in str(payloads)
    q.close()


@pytest.mark.parametrize("role,readonly", [("app", True), ("owner", False)])
def test_collection_rejects_wrong_visibility_or_writable_transaction(db, tmp_path, role, readonly):
    q = ScoreQueue(tmp_path / "queue.db", "fixture")
    with psycopg.connect(db["owner"] if role == "owner" else db["users"][role]) as conn:
        conn.read_only = readonly
        with pytest.raises(ValueError, match="read-only"):
            harvest_feedback(conn, q)
    q.close()


def test_uncommitted_feedback_never_exported(db, tmp_path):
    q = ScoreQueue(tmp_path / "queue.db", "fixture")
    with psycopg.connect(db["users"]["app"]) as writer:
        store = PgTraceStore(writer)
        store.record(trace("d" * 32), None)
        store.add_feedback(
            FeedbackRecord("22222222-2222-4222-8222-222222222222", "d" * 32, "p", "down", None, datetime.now(UTC)), None
        )
        collect(db, q)
        assert '"traceId":"' + "d" * 32 + '"' not in str(q.conn.execute("select payload from scores").fetchall())
        writer.rollback()
    q.close()
