"""M2-03 on the real schema (migration 0008): the operation-key ledger under the application LOGIN user.
Claim-before-run wins or sees the existing row; a succeeded result is reused and immutable; a failed or stale
claim is re-claimed with claim_no + 1; attempts are append-only and unique per (key, claim, attempt); the
run_kind constraint keeps replays and production apart; the read-only role cannot see the ledger at all."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.errors import CheckViolation, InsufficientPrivilege, RestrictViolation, UniqueViolation

from medops.harness.contracts import NodeAttempt
from medops.harness.executions import PgExecutionStore
from tests.integration.lexical_adapter_suite import make_database

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
TRACE = "a" * 32


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


def key(n: int) -> str:
    return f"{n:064x}"


def claim(store: PgExecutionStore, k: str, *, run_id: str = TRACE, node: str = "retrieve", now: datetime = NOW):
    return store.claim(
        operation_key=k,
        operation_scope="harness",
        run_id=run_id,
        trace_id=TRACE,
        node_name=node,
        versions={"policy_version": "p1"},
        now=now,
    )


def attempt(k: str, n: int, outcome: str = "ok") -> NodeAttempt:
    return NodeAttempt(node="retrieve", attempt=n, operation_key=k, started_at=NOW, duration_ms=1.5, outcome=outcome)


def test_claim_complete_reuse_and_attempts_under_the_app_role(db):
    k = key(1)
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgExecutionStore(conn)
        first = claim(store, k)
        assert first.kind == "new" and first.claim_no == 1
        store.record_attempts(1, [attempt(k, 1)])
        store.complete(k, {"state_delta": {"evidence": []}, "flagged": []}, NOW)
        conn.commit()
        again = claim(store, k)
        assert again.kind == "reused" and again.result == {"state_delta": {"evidence": []}, "flagged": []}
        rows = conn.execute(
            "select claim_no, attempt, outcome from operation_attempts where operation_key = %s", (k,)
        ).fetchall()
        assert rows == [(1, 1, "ok")]
        with pytest.raises(UniqueViolation):
            store.record_attempts(1, [attempt(k, 1)])
        conn.rollback()


def test_running_claim_is_in_flight_for_others_until_stale_then_reclaimed(db):
    k = key(2)
    with psycopg.connect(db["users"]["app"]) as a, psycopg.connect(db["users"]["app"]) as b:
        assert claim(PgExecutionStore(a), k).kind == "new"
        a.commit()
        assert claim(PgExecutionStore(b), k).kind == "in_flight"
        b.rollback()
        late = claim(PgExecutionStore(b, stale_after_s=60), k, now=NOW + timedelta(minutes=5))
        assert late.kind == "retry" and late.claim_no == 2
        b.commit()


def test_failed_claim_is_reclaimed_and_succeeded_rows_are_immutable(db):
    k = key(3)
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgExecutionStore(conn)
        claim(store, k)
        store.record_attempts(1, [attempt(k, 1, "timeout"), attempt(k, 2, "failed")])
        store.fail(k, "dependency_timeout", NOW)
        conn.commit()
        retry = claim(store, k, now=NOW + timedelta(seconds=1))
        assert retry.kind == "retry" and retry.claim_no == 2
        store.record_attempts(2, [attempt(k, 1)])
        store.complete(k, {"state_delta": {}, "flagged": []}, NOW)
        conn.commit()
        assert conn.execute("select count(*) from operation_attempts where operation_key = %s", (k,)).fetchone()[0] == 3
        for sql in (
            "update operation_executions set status = 'running' where operation_key = %s",
            "update operation_executions set result = '{}'::jsonb where operation_key = %s",
            "delete from operation_executions where operation_key = %s",
            "update operation_attempts set outcome = 'ok' where operation_key = %s",
            "delete from operation_attempts where operation_key = %s",
        ):
            with pytest.raises((RestrictViolation, InsufficientPrivilege)):  # no DELETE grant for the app role
                conn.execute(sql, (k,))
            conn.rollback()


def test_run_kind_and_result_constraints(db):
    with psycopg.connect(db["users"]["app"]) as conn:
        for kind, run_id in (("production", "b" * 32), ("replay", TRACE)):
            with pytest.raises(CheckViolation):
                conn.execute(
                    "insert into operation_executions (operation_key, operation_scope, run_id, trace_id, run_kind, node_name, versions, status, claimed_at) values (%s, 'harness', %s, %s, %s, 'intent', '{}'::jsonb, 'running', now())",
                    (key(4), run_id, TRACE, kind),
                )
            conn.rollback()
        with pytest.raises(CheckViolation):
            conn.execute(
                "insert into operation_executions (operation_key, operation_scope, run_id, trace_id, run_kind, node_name, versions, status, claimed_at) values (%s, 'harness', %s, %s, 'production', 'intent', '{}'::jsonb, 'succeeded', now())",
                (key(5), TRACE, TRACE),
            )
        conn.rollback()
        assert claim(PgExecutionStore(conn), key(6), run_id=uuid.uuid4().hex).kind == "new"
        assert (
            conn.execute("select run_kind from operation_executions where operation_key = %s", (key(6),)).fetchone()[0]
            == "replay"
        )
        conn.rollback()


def test_read_only_role_has_no_access_and_admin_reads_only(db):
    with psycopg.connect(db["users"]["readonly"]) as ro:
        with pytest.raises(InsufficientPrivilege):
            ro.execute("select count(*) from operation_executions")
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute("select count(*) from operation_executions").fetchone()
        with pytest.raises(InsufficientPrivilege):
            admin.execute(
                "insert into operation_attempts (operation_key, claim_no, attempt, outcome, started_at, duration_ms) values (%s, 1, 1, 'ok', now(), 0)",
                (key(1),),
            )
