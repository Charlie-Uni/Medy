"""Stable source bindings, legacy cutover, crash windows and clone separation."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest

from medops.infrastructure.db.fact_plane import canonical_fact_plane_id
from medops.infrastructure.feedback_identity import feedback_namespace
from medops.infrastructure.observability import ScoreQueue, feedback_event

SOURCE = "11111111-1111-4111-8111-111111111111"
CLONE = "22222222-2222-4222-8222-222222222222"
LEGACY = "a" * 64


def old_event():
    return feedback_event(
        {"feedback_id": SOURCE, "trace_id": "a" * 32, "signal": "up", "created_at": datetime(2026, 10, 8, tzinfo=UTC)},
        fact_plane=LEGACY,
    )


@pytest.mark.parametrize("value", ["", "0" * 64, "00000000-0000-0000-0000-000000000000", SOURCE.replace("-", ""), None])
def test_identity_rejects_missing_nil_and_noncanonical_uuid(value):
    with pytest.raises(ValueError, match="UUID"):
        canonical_fact_plane_id(value)


def test_new_identity_survives_queue_restart_and_has_independent_clone_namespace(tmp_path):
    path = tmp_path / "q.db"
    q = ScoreQueue(path, "project")
    assert feedback_namespace(q.conn, SOURCE) == SOURCE
    q.advance_scan(SOURCE, CLONE)
    q.close()
    q = ScoreQueue(path, "project")
    assert feedback_namespace(q.conn, SOURCE) == SOURCE
    assert q.scan_cursor(SOURCE) == CLONE
    assert feedback_namespace(q.conn, CLONE) == CLONE
    assert q.scan_cursor(CLONE) == "00000000-0000-0000-0000-000000000000"
    q.close()


@pytest.mark.parametrize("with_cursor", [True, False])
def test_legacy_binding_is_explicit_preserves_payload_and_cannot_be_claimed_twice(tmp_path, with_cursor):
    q = ScoreQueue(tmp_path / "q.db", "project")
    event = old_event()
    q.enqueue(event)
    if with_cursor:
        q.advance_scan(LEGACY, CLONE)
    before = q.conn.execute("select id,payload,updated_at from scores").fetchall()
    with pytest.raises(ValueError, match="explicit source binding"):
        feedback_namespace(q.conn, SOURCE)
    assert q.conn.execute("select count(*) from feedback_sources").fetchone()[0] == 0
    assert feedback_namespace(q.conn, SOURCE, legacy_source=LEGACY) == LEGACY
    assert feedback_namespace(q.conn, SOURCE) == LEGACY
    assert q.scan_cursor(SOURCE) == "00000000-0000-0000-0000-000000000000"
    assert not q.enqueue(event)
    assert q.conn.execute("select id,payload,updated_at from scores").fetchall() == before
    with pytest.raises(ValueError, match="immutable"):
        feedback_namespace(q.conn, SOURCE, legacy_source="b" * 64)
    with pytest.raises(ValueError, match="another fact plane"):
        feedback_namespace(q.conn, CLONE, legacy_source=LEGACY)
    q.close()


def test_legacy_namespace_survives_receipt_eviction_and_queue_reopen(tmp_path):
    path = tmp_path / "q.db"
    q = ScoreQueue(path, "project", max_rows=1)
    original = old_event()
    q.enqueue(original)
    feedback_namespace(q.conn, SOURCE, legacy_source=LEGACY)
    q.conn.execute("update scores set delivered=1")
    q.conn.commit()
    alternate = feedback_event(
        {"feedback_id": CLONE, "trace_id": "b" * 32, "signal": "down", "created_at": datetime(2026, 10, 8, tzinfo=UTC)},
        fact_plane=CLONE,
    )
    q.enqueue(alternate)  # Evicts the transport receipt, never the source binding.
    q.conn.execute("update scores set delivered=1")
    q.conn.commit()
    q.close()
    q = ScoreQueue(path, "project", max_rows=1)
    restored = old_event()
    assert restored["body"]["metadata"]["fact_plane"] == feedback_namespace(q.conn, SOURCE)
    assert q.enqueue(restored)
    assert json.loads(q.conn.execute("select payload from scores").fetchone()[0]) == original
    q.close()


def test_ambiguous_unbound_legacy_source_does_not_get_guessed(tmp_path):
    q = ScoreQueue(tmp_path / "q.db", "project")
    q.advance_scan(LEGACY, SOURCE)
    q.advance_scan("b" * 64, SOURCE)
    feedback_namespace(q.conn, SOURCE, legacy_source=LEGACY)
    with pytest.raises(ValueError, match="explicit source binding"):
        feedback_namespace(q.conn, CLONE)
    with pytest.raises(ValueError, match="runtime hash"):
        feedback_namespace(q.conn, CLONE, legacy_source="guess")
    q.close()


@pytest.mark.parametrize("same_source", [True, False])
def test_concurrent_binding_serializes_and_cannot_assign_one_legacy_namespace_twice(tmp_path, same_source):
    path = tmp_path / "q.db"
    ScoreQueue(path, "project").close()
    barrier = threading.Barrier(2)

    def bind(source):
        q = ScoreQueue(path, "project")
        try:
            barrier.wait(timeout=5)
            try:
                return feedback_namespace(q.conn, source, legacy_source=LEGACY)
            except ValueError:
                return "refused"
        finally:
            q.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(bind, (SOURCE, SOURCE if same_source else CLONE)))
    assert sorted(results) == sorted([LEGACY, LEGACY if same_source else "refused"])
    q = ScoreQueue(path, "project")
    assert q.conn.execute("select count(*) from feedback_sources").fetchone()[0] == 1
    q.close()
