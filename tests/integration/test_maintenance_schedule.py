"""The scheduler adapter respects real PostgreSQL roles, locking, rollback and late feedback."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import psycopg
from psycopg import errors
from psycopg.types.json import Jsonb

from medops.worker.maintenance import execute


def test_loop_job_collects_late_feedback_idempotently_without_release_access(migrated, login_users):
    tid = uuid.uuid4().hex
    with psycopg.connect(migrated) as admin:
        admin.execute(
            "insert into traces(trace_id,run_id,kind,principal,dept,query,outcome,reason_codes,versions,"
            "model_calls,tokens,cost_usd,duration_ms,created_at) values (%s,%s,'ask',%s,'PV','synthetic','answered','{}',%s,0,0,0,0,'2000-01-01')",
            (tid, tid, "a" * 32, Jsonb({})),
        )
        admin.execute(
            "insert into feedback(feedback_id,trace_id,principal,signal) values (%s,%s,%s,'down')",
            (uuid.uuid4(), tid, "a" * 32),
        )
    loop_dsn = login_users["loop"]["dsn"]
    with psycopg.connect(loop_dsn) as loop:
        with loop.transaction(force_rollback=True):
            report = execute(loop, None, job="loop-observe", since=datetime(1970, 1, 1, tzinfo=UTC), dry_run=True)
            assert report["opened"] >= 1
    with psycopg.connect(migrated) as admin:
        assert admin.execute("select count(*) from bad_cases where trace_id=%s", (tid,)).fetchone()[0] == 0
    for _ in range(2):
        with psycopg.connect(loop_dsn) as loop:
            execute(loop, None, job="loop-observe", since=datetime(1970, 1, 1, tzinfo=UTC), dry_run=False)
    with psycopg.connect(migrated) as admin:
        assert admin.execute("select count(*) from bad_cases where trace_id=%s", (tid,)).fetchone()[0] == 1
    with psycopg.connect(loop_dsn) as loop:
        import pytest

        with pytest.raises(errors.InsufficientPrivilege):
            execute(loop, SimpleNamespace(trace_retention_days=365), job="audit-retention", since=None, dry_run=True)


def test_duplicate_schedules_are_locked_only_until_the_transaction_ends(migrated):
    with psycopg.connect(migrated) as first, psycopg.connect(migrated) as second:
        # Payload expiry reads are legitimate without a KEK; deleting ciphertext never decrypts it.
        settings = SimpleNamespace(escalation_payload_grace_days=30)
        assert "deleted" in execute(first, settings, job="payload-retention", since=None, dry_run=True)
        assert execute(second, settings, job="payload-retention", since=None, dry_run=True) == {
            "status": "already_running"
        }
        first.rollback()
        assert "deleted" in execute(second, settings, job="payload-retention", since=None, dry_run=True)
        second.rollback()
