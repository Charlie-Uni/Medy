"""M3-07 / DEC-013 on a real database: the application role can only insert restricted payloads, the restricted role
reads them and logs access, the admin role sees only the access log, and the retention purge respects escalations."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from medops.core.envelope import StaticKeyProvider, payload_aad, seal
from medops.infrastructure.db.payloads import PgPayloadStore
from tests.integration.lexical_adapter_suite import make_database

PROVIDER = StaticKeyProvider({"k1": secrets.token_bytes(32)}, "k1")
PRINCIPAL = "a" * 64


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


def _trace(conn, trace_id: str, *, escalation: str | None = None, handled_at: datetime | None = None) -> None:
    conn.execute(
        "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, reason_codes, versions, model_calls, tokens, cost_usd, duration_ms) "
        "values (%s, %s, 'ask', %s, 'MA', 'q', %s, %s, %s, 0, 0, 0, 1)",
        (
            trace_id,
            trace_id,
            PRINCIPAL,
            "escalated" if escalation else "answered",
            ["insufficient_evidence"] if escalation else [],
            Jsonb({}),
        ),
    )
    if escalation:
        conn.execute(
            "insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, policy_version, status, handled_by, handled_at) "
            "values (%s, %s, %s, 'MA', %s, 'q', 'p', %s, %s, %s)",
            (
                uuid.uuid4().hex,
                trace_id,
                PRINCIPAL,
                ["insufficient_evidence"],
                escalation,
                "h" * 32 if handled_at else None,
                handled_at,
            ),
        )


def _put(conn, trace_id: str, expires_at: datetime) -> None:
    sealed = seal(b'{"query": "q"}', aad=payload_aad(trace_id, "ask", "input"), provider=PROVIDER)
    PgPayloadStore(conn).put(trace_id, "ask", "input", sealed, expires_at)


def test_roles_and_retention(db):
    now = datetime.now(UTC)
    t_live, t_expired, t_open, t_closed_recent, t_closed_old = (uuid.uuid4().hex for _ in range(5))
    with psycopg.connect(db["users"]["app"]) as app:
        for tid in (t_live, t_expired):
            _trace(app, tid)
        _trace(app, t_open, escalation="open")
        _trace(app, t_closed_recent, escalation="closed", handled_at=now - timedelta(days=5))
        _trace(app, t_closed_old, escalation="closed", handled_at=now - timedelta(days=60))
        _put(app, t_live, now + timedelta(days=90))
        for tid in (t_expired, t_open, t_closed_recent, t_closed_old):
            _put(app, tid, now - timedelta(days=1))
        app.commit()
        with pytest.raises(pg_errors.InsufficientPrivilege):  # the application role writes but never reads
            app.execute("select count(*) from trace_payloads")
        app.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        with pytest.raises(pg_errors.InsufficientPrivilege):  # the admin role never sees ciphertext or wrapped keys
            admin.execute("select ciphertext, dek_wrapped from trace_payloads")
        admin.rollback()
    with psycopg.connect(db["users"]["restricted"]) as restricted:
        store = PgPayloadStore(restricted)
        rows = store.list(t_live)
        assert len(rows) == 1 and rows[0]["sealed"].kek_version == "k1"
        store.log_access(PRINCIPAL, t_live, "incident review 42")
        restricted.commit()  # the access log row must survive the failing statement below
        with pytest.raises(
            pg_errors.InsufficientPrivilege
        ):  # restricted reads and rewraps (0019): only those two columns
            restricted.execute("update trace_payloads set ciphertext = %s", (b"x",))
        restricted.rollback()
        deleted = store.purge(now, escalation_grace_days=30)
        restricted.commit()
        # expired without escalation and closed-beyond-grace go; live, open and closed-within-grace stay
        assert deleted == 2
        remaining = {r[0] for r in restricted.execute("select trace_id from trace_payloads")}
        assert remaining == {t_live, t_open, t_closed_recent}
        with pytest.raises((pg_errors.RaiseException, pg_errors.InsufficientPrivilege)):  # access log is append-only
            restricted.execute("delete from payload_access_log")
        restricted.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        log = admin.execute(
            "select principal, purpose from payload_access_log where trace_id = %s", (t_live,)
        ).fetchall()
        assert log == [(PRINCIPAL, "incident review 42")]
