"""Fact hashes detect meaningful database changes while ignoring maintenance bookkeeping."""

import psycopg
import pytest

from medops.evals.run_conditions import fact_snapshot
from medops.ingestion import outbox
from tests.integration.test_lexical_production import db as db  # noqa: F401 - isolated module database
from tests.integration.test_lexical_production import seed as seed  # noqa: F401


def capture(dsn):
    with psycopg.connect(dsn) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        return fact_snapshot(conn)


def test_snapshot_is_stable_across_read_sessions_and_outbox_bookkeeping(db, seed):
    before = capture(db["users"]["admin"])
    assert before == capture(db["users"]["admin"])
    with psycopg.connect(db["users"]["admin"]) as conn:
        doc, family = conn.execute("select doc_id,family_id from documents where status='active' limit 1").fetchone()
        event = outbox.emit(
            conn,
            "document_acl_changed",
            aggregate_id=doc,
            family_id=family,
            payload={"acl_depts": ["MA"]},
            actor="fixture",
        )
        outbox.ack(conn, "lexical-index", event)
        conn.execute("update lexical_index_meta set built_at=now(),built_by='maintenance-fixture',chunk_count=0")
        conn.commit()
    assert before == capture(db["users"]["admin"])


def test_actual_acl_and_index_version_changes_alter_different_fact_sections(db, seed):
    dsn = db["users"]["admin"]
    before = capture(dsn)
    with psycopg.connect(dsn) as conn:
        doc = conn.execute("select doc_id from documents where owner_dept='MA' and status='active' limit 1").fetchone()[
            0
        ]
        conn.execute("insert into document_acl(doc_id,dept,granted_by) values(%s,'CO','fixture')", (doc,))
        conn.commit()
    acl_changed = capture(dsn)
    assert before["sha256"] != acl_changed["sha256"]
    assert before["tables"]["document_acl"] != acl_changed["tables"]["document_acl"]
    assert before["tables"]["chunks"] == acl_changed["tables"]["chunks"]
    with psycopg.connect(dsn) as conn:
        conn.execute("update lexical_index_meta set dictionary_version='fixture-drift'")
        conn.commit()
    changed = capture(dsn)
    assert changed["tables"]["lexical_index_meta"] != acl_changed["tables"]["lexical_index_meta"]


@pytest.mark.parametrize("read_only,isolation", [(False, psycopg.IsolationLevel.REPEATABLE_READ), (True, None)])
def test_snapshot_requires_consistent_read_only_transaction(db, seed, read_only, isolation):
    with psycopg.connect(db["owner"]) as conn:
        conn.read_only = read_only
        conn.isolation_level = isolation
        with pytest.raises(ValueError, match="read-only repeatable-read"):
            fact_snapshot(conn)


def test_rls_empty_corpus_cannot_be_registered_as_the_global_fact_identity(db, seed):
    with psycopg.connect(db["users"]["app"]) as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        with pytest.raises(ValueError, match="global administrative"):
            fact_snapshot(conn)
