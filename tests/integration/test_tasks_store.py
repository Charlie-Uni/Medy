"""PgTaskStore on migration 0010 under the application LOGIN user: idempotent creation (same key wins once, a
concurrent duplicate raises IdempotencyRace and leaves the transaction usable), atomic claims with leases,
late reports from a worker that lost its lease are ignored, attempts are recorded, exhausted tasks fail closed,
and the read-only role has no access."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg.errors import InsufficientPrivilege

from medops.api.contracts import TaskStatus
from medops.application.tasks import IdempotencyRace, TaskRecord
from medops.domain.common import Dept
from medops.infrastructure.db.tasks import PgTaskStore
from tests.integration.lexical_adapter_suite import make_database

NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
PRINCIPAL = "0123456789abcdef" * 2  # pseudonyms are hex (migration 0010 check)


@pytest.fixture
def db(admin_dsn: str) -> Iterator[dict]:
    """One fresh database per test: tasks are never deleted, so leftovers would be claimable by the next test."""
    yield from make_database(admin_dsn)


def record(task_id: str, text: str = "hi", max_attempts: int = 3) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        principal=PRINCIPAL,
        dept=Dept.PV,
        skill_name="echo_skill",
        skill_version="1.0.0",
        input={"text": text},
        status=TaskStatus.queued,
        created_at=NOW,
        updated_at=NOW,
        max_attempts=max_attempts,
    )


def test_idempotent_create_and_race(db):
    import uuid

    t1, t2 = str(uuid.uuid4()), str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTaskStore(conn)
        store.create(record(t1), ("POST /v1/tasks", "key-1", NOW + timedelta(days=1)))
        conn.commit()
        found = store.find_idempotent(PRINCIPAL, "POST /v1/tasks", "key-1")
        assert found is not None and found[1] == t1 and len(found[0]) == 64
        with pytest.raises(IdempotencyRace):
            store.create(record(t2), ("POST /v1/tasks", "key-1", NOW + timedelta(days=1)))
        # the outer transaction survived the losing insert (savepoint)
        assert store.get(t1) is not None and store.get(t2) is None
        conn.commit()
        assert (
            store.find_idempotent("fedcba9876543210" * 2, "POST /v1/tasks", "key-1") is None
        )  # other principal, other scope


def test_claim_lease_finish_and_lost_report(db):
    import uuid

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as a, psycopg.connect(db["users"]["app"]) as b:
        sa, sb = PgTaskStore(a), PgTaskStore(b)
        sa.create(record(tid), None)
        a.commit()
        claimed = sa.claim_next("w1", 60, NOW)
        a.commit()
        assert claimed is not None and claimed.task_id == tid and claimed.attempts == 1 and claimed.lease_owner == "w1"
        assert sb.claim_next("w2", 60, NOW) is None  # leased
        b.rollback()
        reclaimed = sb.claim_next("w2", 60, NOW + timedelta(seconds=61))
        b.commit()
        assert reclaimed is not None and reclaimed.attempts == 2 and reclaimed.lease_owner == "w2"
        assert sa.complete(tid, "w1", 1, "a" * 32, {"x": 1}, NOW + timedelta(seconds=62)) is False  # w1 lost the lease
        a.rollback()
        assert sb.complete(tid, "w2", 2, "b" * 32, {"skill": "echo_skill@1.0.0"}, NOW + timedelta(seconds=70)) is True
        b.commit()
        final = sa.get(tid)
        assert final is not None and final.status is TaskStatus.completed and final.trace_id == "b" * 32
        rows = a.execute(
            "select attempt, worker, outcome from task_attempts where task_id = %s order by attempt", (tid,)
        ).fetchall()
        assert rows == [(1, "w1", "lost"), (2, "w2", "completed")]


def test_exhausted_tasks_fail_closed_and_requeue_only_from_failed(db):
    import uuid

    tid = str(uuid.uuid4())
    with psycopg.connect(db["users"]["app"]) as conn:
        store = PgTaskStore(conn)
        store.create(record(tid, max_attempts=1), None)
        conn.commit()
        assert store.claim_next("w1", 10, NOW) is not None
        conn.commit()
        assert store.claim_next("w2", 10, NOW + timedelta(seconds=11)) is None  # lease expired, attempts exhausted
        conn.commit()
        failed = store.get(tid)
        assert failed is not None and failed.status is TaskStatus.failed and failed.error["retryable"] is False
        assert store.requeue(tid, NOW) is not None and store.get(tid).status is TaskStatus.queued
        assert store.requeue(tid, NOW) is None  # not failed any more
        conn.rollback()


def test_read_only_role_has_no_access(db):
    with psycopg.connect(db["users"]["readonly"]) as ro:
        for table in ("tasks", "task_attempts", "idempotency_keys"):
            with pytest.raises(InsufficientPrivilege):
                ro.execute(f"select count(*) from {table}")  # noqa: S608 - fixed table names
            ro.rollback()
