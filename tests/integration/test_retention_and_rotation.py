"""Migration 0019 (M5-06): the audit tables stay append-only except for the admin role's retention purge (gated by two
transaction-local settings, floor 90 days, open escalations and ticketed cases keep their traces), and encrypted
payloads change only by a KEK rewrap on the restricted role (ciphertext untouched, still decryptable)."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from medops.application.payload_rotation import rotate
from medops.application.retention import purge
from medops.core.envelope import StaticKeyProvider, open_sealed, payload_aad, seal
from medops.infrastructure.db.payloads import PgPayloadStore

PRINCIPAL = "e" * 32


def _trace(conn, trace_id: str, *, age_days: int, dept: str = "MA") -> None:
    conn.execute(
        "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, reason_codes, versions, "
        "model_calls, tokens, cost_usd, duration_ms, created_at) values (%s, %s, 'ask', %s, %s, 'q', 'answered', '{}', %s, 0, 0, 0, 0, %s)",
        (trace_id, trace_id, PRINCIPAL, dept, Jsonb({}), datetime.now(UTC) - timedelta(days=age_days)),
    )
    conn.execute(
        "insert into trace_spans (trace_id, node, attempt, operation_key, outcome, started_at, duration_ms) "
        "values (%s, 'intent', 1, %s, 'ok', %s, 1)",
        (trace_id, uuid.uuid4().hex + uuid.uuid4().hex, datetime.now(UTC) - timedelta(days=age_days)),  # 64 hex
    )


def _escalation(conn, trace_id: str, *, status: str, age_days: int) -> None:
    conn.execute(
        "insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, evidence_chunk_ids, "
        "policy_version, detail, status, created_at) values (%s, %s, %s, 'MA', '{insufficient_evidence}', 'q', '{}', 'p', 'd', %s, %s)",
        (trace_id, trace_id, PRINCIPAL, status, datetime.now(UTC) - timedelta(days=age_days)),
    )


@pytest.fixture(scope="module")
def seeded(migrated, login_users):
    ids = {k: uuid.uuid4().hex for k in ("old", "young", "old_open", "old_closed", "old_ticket")}
    with psycopg.connect(migrated) as conn:
        _trace(conn, ids["old"], age_days=400)
        conn.execute(
            "insert into feedback (feedback_id, trace_id, principal, signal, created_at) values (%s, %s, %s, 'up', %s)",
            (uuid.uuid4(), ids["old"], PRINCIPAL, datetime.now(UTC) - timedelta(days=400)),
        )
        _trace(conn, ids["young"], age_days=10)
        _trace(conn, ids["old_open"], age_days=400)
        _escalation(conn, ids["old_open"], status="open", age_days=400)
        _trace(conn, ids["old_closed"], age_days=400)
        _escalation(conn, ids["old_closed"], status="closed", age_days=400)
        _trace(conn, ids["old_ticket"], age_days=400)
        case_id = conn.execute(
            "insert into bad_cases (trace_id, dept, opened_at, signals, label, reasons, attribution, status) "
            "values (%s, 'MA', %s, %s, 'bad', '{feedback_down}', 'knowledge_gap', 'attributed') returning case_id",
            (ids["old_ticket"], datetime.now(UTC) - timedelta(days=400), Jsonb({})),
        ).fetchone()[0]
        conn.execute(
            "insert into document_requests (case_id, dept, topic, gap, requested_by) values (%s, 'MA', 'q', 'gap', 'loop')",
            (case_id,),
        )
        conn.commit()
    return {"ids": ids, "users": {k: v["dsn"] for k, v in login_users.items()}}


def test_audit_rows_stay_append_only_outside_a_purge_transaction(seeded):
    ids = seeded["ids"]
    with psycopg.connect(seeded["users"]["admin"]) as admin:
        with pytest.raises(pg_errors.RestrictViolation):  # admin may delete, but only inside a purge transaction
            admin.execute("delete from traces where trace_id = %s", (ids["old"],))
        admin.rollback()
        admin.execute("select set_config('medops.retention_purge', 'on', true)")
        admin.execute(
            "select set_config('medops.retention_days', '30', true)"
        )  # floor is 90: still refused for 10 days
        with pytest.raises(pg_errors.RestrictViolation):
            admin.execute("delete from trace_spans where trace_id = %s", (ids["young"],))
        admin.rollback()
    with psycopg.connect(seeded["users"]["app"]) as app:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            app.execute("delete from traces where trace_id = %s", (ids["old"],))


def test_retention_purge_keeps_open_escalations_and_ticketed_cases(seeded):
    ids = seeded["ids"]
    with psycopg.connect(seeded["users"]["admin"]) as admin:
        with pytest.raises(ValueError):
            purge(admin, days=30)
        report = purge(admin, days=365, dry_run=True)
        admin.rollback()
        assert report.candidates >= 2 and report.deleted["traces"] >= 2
        with psycopg.connect(seeded["users"]["admin"]) as check:
            assert (
                check.execute("select count(*) from traces where trace_id = %s", (ids["old"],)).fetchone()[0] == 1
            )  # dry run
        report = purge(admin, days=365)
        admin.commit()
        left = {
            r[0]
            for r in admin.execute(
                "select trace_id from traces where trace_id = any(%s)", (list(ids.values()),)
            ).fetchall()
        }
    assert ids["old"] not in left and ids["old_closed"] not in left  # old, and old with a closed escalation
    assert {ids["young"], ids["old_open"], ids["old_ticket"]} <= left  # young / open escalation / ticketed case stay
    assert report.deleted["feedback"] >= 1 and report.deleted["escalations"] >= 1 and report.deleted["trace_spans"] >= 2


def test_payload_rotation_rewraps_without_touching_ciphertext(migrated, login_users):
    k1, k2 = secrets.token_bytes(32), secrets.token_bytes(32)
    before = StaticKeyProvider({"k1": k1}, "k1")
    after = StaticKeyProvider({"k1": k1, "k2": k2}, "k2")
    trace_id = uuid.uuid4().hex
    with psycopg.connect(migrated) as conn:
        _trace(conn, trace_id, age_days=1)
        conn.commit()
    with psycopg.connect(login_users["app"]["dsn"]) as app:
        app.execute("select set_config('medops.dept', 'MA', true)")
        sealed = seal(b'{"input": "q"}', aad=payload_aad(trace_id, "ask", "input"), provider=before)
        PgPayloadStore(app).put(trace_id, "ask", "input", sealed, datetime.now(UTC) + timedelta(days=90))
        app.commit()
    with psycopg.connect(login_users["restricted"]["dsn"]) as restricted:
        store = PgPayloadStore(restricted)
        assert store.count_stale("k2") >= 1
        dry = rotate(restricted, after, dry_run=True)
        restricted.rollback()
        assert dry.rewrapped >= 1 and store.count_stale("k2") >= 1
        report = rotate(restricted, after)
        restricted.commit()
        assert report.stale_before >= 1 and report.rewrapped == report.stale_before and store.count_stale("k2") == 0
        stored = next(r for r in store.list(trace_id) if r["kind"] == "input")["sealed"]
        assert stored.kek_version == "k2" and stored.ciphertext == sealed.ciphertext and stored.nonce == sealed.nonce
        assert open_sealed(stored, aad=payload_aad(trace_id, "ask", "input"), provider=after) == b'{"input": "q"}'
        with pytest.raises(pg_errors.InsufficientPrivilege):  # only the two rewrap columns are granted
            restricted.execute("update trace_payloads set ciphertext = %s where trace_id = %s", (b"x", trace_id))
        restricted.rollback()
    with psycopg.connect(migrated) as su:  # even a superuser cannot rewrite content: the 0019 guard is defence in depth
        with pytest.raises(pg_errors.RestrictViolation):
            su.execute("update trace_payloads set ciphertext = %s where trace_id = %s", (b"x", trace_id))
        su.rollback()
