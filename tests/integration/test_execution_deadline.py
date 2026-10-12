"""Real PostgreSQL cancellation preserves the outer audit transaction and timeout settings."""

import time

import psycopg
import pytest

from medops.core.deadline import DeadlineExceeded, deadline_scope
from medops.harness.contracts import NodeFailure, NodeSpec, run_node
from medops.infrastructure.db.deadline import DeadlineConnection


def test_first_guarded_statement_does_not_commit_before_caller_rollback(migrated):
    with psycopg.connect(migrated) as conn:
        conn.execute("create table arch15_atomic_probe(value integer)")
    try:
        with pytest.raises(RuntimeError), psycopg.connect(migrated) as conn, deadline_scope(2):
            DeadlineConnection(conn).execute("insert into arch15_atomic_probe values (1)")
            raise RuntimeError("synthetic audit failure")
        with psycopg.connect(migrated) as conn:
            assert conn.execute("select count(*) from arch15_atomic_probe").fetchone() == (0,)
    finally:
        with psycopg.connect(migrated) as conn:
            conn.execute("drop table arch15_atomic_probe")


def test_statement_timeout_rolls_back_only_its_savepoint_and_allows_audit(conn):
    conn.execute("set local statement_timeout = '2s'")
    guarded = DeadlineConnection(DeadlineConnection(conn))  # nested Skill/Ask assembly is safe
    started = time.monotonic()
    with pytest.raises(NodeFailure) as exc:
        run_node(NodeSpec(name="sql", timeout_s=0.05), "proof", lambda: guarded.execute("select pg_sleep(1)"))
    assert time.monotonic() - started < 0.5
    assert exc.value.attempts[-1].error_code == "dependency_timeout"
    assert conn.execute("select current_setting('statement_timeout')").fetchone()[0] == "2s"
    assert conn.execute("select 1 as audit_still_available").fetchone() == (1,)


def test_expired_statement_is_not_dispatched_and_successful_cursor_results_are_preserved(conn):
    conn.execute("set local statement_timeout = '2s'")
    guarded = DeadlineConnection(conn)
    with deadline_scope(1):
        with guarded.cursor() as cursor:
            cursor.execute("select 42")
            assert cursor.fetchone() == (42,)
        assert guarded.execute("select 7").fetchone() == (7,)
        assert list(guarded.execute("select generate_series(1, 3)")) == [(1,), (2,), (3,)]
    with deadline_scope(0.01):
        time.sleep(0.02)
        with pytest.raises(DeadlineExceeded):
            guarded.execute("select pg_sleep(1)")
    assert conn.execute("select current_setting('statement_timeout')").fetchone()[0] == "2s"
