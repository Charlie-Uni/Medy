"""Read-only audit collection, late commits and durable cursor recovery on a disposable DB."""

from datetime import UTC, datetime

import psycopg
import pytest

from medops.application.audit import FeedbackRecord
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.fact_plane import fact_plane_identity, rotate_clone_identity
from medops.infrastructure.observability import ScoreQueue, feedback_event, harvest_feedback
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


def test_reconnect_and_volatile_identity_changes_do_not_change_feedback_ids_or_cursor(db, tmp_path, monkeypatch):
    from medops.retrieval import integrity

    monkeypatch.setattr(integrity, "database_identity", lambda _conn: pytest.fail("volatile identity used"))
    path = tmp_path / "q.db"
    q = ScoreQueue(path, "fixture")
    assert collect(db, q)["enqueued"] >= 2
    before = q.conn.execute("select id,payload from scores order by id").fetchall()
    with psycopg.connect(db["owner"]) as conn:
        identity = fact_plane_identity(conn)
    cursor = q.scan_cursor(identity)
    q.close()
    q = ScoreQueue(path, "fixture")
    assert q.scan_cursor(identity) == cursor
    assert collect(db, q)["sweep_complete"]
    assert collect(db, q)["enqueued"] == 0
    assert q.conn.execute("select id,payload from scores order by id").fetchall() == before
    assert q.conn.execute("select source from scans").fetchall() == [(identity,)]
    q.close()


def test_crash_after_durable_enqueue_before_cursor_replays_without_new_id(db, tmp_path, monkeypatch):
    q = ScoreQueue(tmp_path / "q.db", "fixture")
    advance = q.advance_scan

    def crash(*_args):
        raise RuntimeError("simulated process failure")

    monkeypatch.setattr(q, "advance_scan", crash)
    with pytest.raises(RuntimeError, match="simulated"):
        collect(db, q)
    before = q.conn.execute("select id,payload from scores order by id").fetchall()
    assert len(before) >= 2
    monkeypatch.setattr(q, "advance_scan", advance)
    assert collect(db, q)["enqueued"] == 0
    assert q.conn.execute("select id,payload from scores order by id").fetchall() == before
    q.close()


def test_legacy_cutover_keeps_score_ids_metadata_and_original_timestamp(db, tmp_path):
    q = ScoreQueue(tmp_path / "q.db", "fixture")
    legacy = "b" * 64
    with psycopg.connect(db["owner"]) as conn:
        rows = conn.execute(
            "select feedback_id::text,trace_id,signal,created_at from feedback order by feedback_id"
        ).fetchall()
    for row in rows:
        q.enqueue(
            feedback_event(
                dict(zip(("feedback_id", "trace_id", "signal", "created_at"), row, strict=True)), fact_plane=legacy
            )
        )
    before = q.conn.execute("select id,payload from scores order by id").fetchall()
    with pytest.raises(ValueError, match="explicit source binding"):
        collect(db, q)
    assert collect(db, q, legacy_source=legacy)["enqueued"] == 0
    assert q.conn.execute("select id,payload from scores order by id").fetchall() == before
    q.close()


def test_expected_deployment_identity_mismatch_does_not_touch_queue(db, tmp_path):
    q = ScoreQueue(tmp_path / "q.db", "fixture")
    with pytest.raises(ValueError, match="deployment binding"):
        collect(db, q, expected_fact_plane="33333333-3333-4333-8333-333333333333")
    for table in ("scores", "scans", "feedback_sources"):
        assert q.conn.execute(f"select count(*) from {table}").fetchone()[0] == 0
    q.close()


def test_identity_permissions_and_owner_clone_rotation_are_explicit(db):
    with psycopg.connect(db["owner"]) as conn:
        original = fact_plane_identity(conn)
        with pytest.raises(ValueError, match="deployment binding"), conn.transaction():
            rotate_clone_identity(conn, expected="33333333-3333-4333-8333-333333333333")
        rotated = rotate_clone_identity(conn, expected=original)
        assert rotated != original and fact_plane_identity(conn) == rotated
        conn.rollback()  # Rotation is demonstrated only on the disposable DB, never retained.
        assert fact_plane_identity(conn) == original
    for role in ("admin", "loop"):
        with psycopg.connect(db["users"][role]) as conn:
            assert fact_plane_identity(conn) == original
            with pytest.raises(ValueError, match="migration owner"), conn.transaction():
                rotate_clone_identity(conn, expected=original)
            with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                conn.execute("update fact_plane_identity set fact_plane_id=gen_random_uuid()")
    with psycopg.connect(db["users"]["app"]) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            fact_plane_identity(conn)


def test_identity_migration_has_no_body_changes_and_no_fallback_without_identity(scratch_database):
    from scripts.db_restore_drill import inventory

    from tests.integration.conftest import run_alembic

    run_alembic(scratch_database, "upgrade", "0024")
    with psycopg.connect(scratch_database) as conn:
        with pytest.raises(psycopg.errors.UndefinedTable), conn.transaction():
            fact_plane_identity(conn)
        PgTraceStore(conn).record(trace("c" * 32), None)
        conn.commit()
        before = conn.execute("select row_to_json(t)::text from traces t").fetchall()
    run_alembic(scratch_database, "upgrade", "head")
    restored_inventory = inventory(scratch_database)
    with psycopg.connect(scratch_database) as conn:
        identity = fact_plane_identity(conn)
        assert restored_inventory["fact_plane_id"] == identity
        assert conn.execute("select row_to_json(t)::text from traces t").fetchall() == before
    run_alembic(scratch_database, "downgrade", "0024")
    with psycopg.connect(scratch_database) as conn:
        assert conn.execute("select row_to_json(t)::text from traces t").fetchall() == before
        with pytest.raises(psycopg.errors.UndefinedTable), conn.transaction():
            fact_plane_identity(conn)
    run_alembic(scratch_database, "upgrade", "head")
    with psycopg.connect(scratch_database) as conn:
        assert fact_plane_identity(conn) != identity  # Downgrade loses the source; it is not a safe routine rollback.
        assert conn.execute("select row_to_json(t)::text from traces t").fetchall() == before
