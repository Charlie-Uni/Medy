"""Published documents become searchable after retry; failed events cannot acquire an ACK."""

import psycopg
import pytest

from medops.ingestion import outbox
from medops.retrieval import maintenance, production
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.embedding import EMBEDDING_VERSION, HashingEmbeddingProvider
from tests.integration.test_lexical_production import db as db  # noqa: F401 - isolated module database
from tests.integration.test_lexical_production import seed as seed  # noqa: F401


@pytest.fixture
def connection(db, seed):
    with psycopg.connect(db["users"]["admin"]) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def provider(connection):
    provider = HashingEmbeddingProvider(embedding_version=EMBEDDING_VERSION)
    pg_vector.build_index(connection, provider, built_by="test-only", doc_ids=[])
    return provider


def emit(conn, *, status="active", event_type="document_activated"):
    doc, family, dept = conn.execute(
        "select doc_id,family_id,owner_dept::text from documents where status=%s order by doc_id limit 1", (status,)
    ).fetchone()
    eid = outbox.emit(conn, event_type, aggregate_id=doc, family_id=family, payload={"acl_depts": [dept]}, actor="test")
    return doc, eid


def indexed(conn, doc, table):
    return conn.execute(
        f"select count(*) from {table} i join chunks c using(chunk_id) where c.doc_id=%s", (doc,)
    ).fetchone()[0]


def lexical_indexed(conn, doc):
    return sum(indexed(conn, doc, table) for table in production.PRODUCTION_LEXICAL_TABLES.values())


def expected_lexical_assignments(conn, doc):
    return conn.execute(
        "select count(*) from chunks c join document_acl a on a.doc_id=c.doc_id and a.permission='read' "
        "where c.doc_id=%s",
        (doc,),
    ).fetchone()[0]


def test_missing_indexes_recover_idempotently_and_vector_work_is_document_scoped(connection, provider):
    conn = connection
    doc, eid = emit(conn)
    count = conn.execute("select count(*) from chunks where doc_id=%s", (doc,)).fetchone()[0]
    assignments = expected_lexical_assignments(conn, doc)
    for table in production.PRODUCTION_LEXICAL_TABLES.values():
        conn.execute(f"delete from {table} l using chunks c where c.chunk_id=l.chunk_id and c.doc_id=%s", (doc,))
    for name, handler in (
        ("lexical-index", maintenance.lexical_handler()),
        ("vector-index", maintenance.vector_handler(provider)),
    ):
        first = maintenance.consume_batch(conn, name, handler)
        assert first.acknowledged == (eid,) and not first.failed
        assert not maintenance.consume_batch(conn, name, handler).acknowledged
    assert lexical_indexed(conn, doc) == assignments
    assert indexed(conn, doc, "chunk_embeddings") == count
    assert conn.execute("select count(*) from chunk_embeddings").fetchone()[0] == count


def test_partial_vector_failure_rolls_back_writes_and_ack_then_retry_recovers(connection, provider, monkeypatch):
    conn = connection
    doc, eid = emit(conn)
    original = pg_vector.build_index

    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("sensitive SQL/DSN/prompt must never be saved")

    monkeypatch.setattr(pg_vector, "build_index", fail_after_write)
    failed = maintenance.consume_batch(
        conn, "vector-index", maintenance.vector_handler(provider), backoff_base_s=0, backoff_max_s=0
    )
    assert failed.failed == (eid,) and not failed.acknowledged
    assert indexed(conn, doc, "chunk_embeddings") == 0
    assert conn.execute("select attempts,last_error from outbox_events where event_id=%s", (eid,)).fetchone() == (
        1,
        "vector-index:RuntimeError",
    )
    assert conn.execute("select count(*) from outbox_consumer_acks where event_id=%s", (eid,)).fetchone()[0] == 0
    monkeypatch.setattr(pg_vector, "build_index", original)
    assert maintenance.consume_batch(conn, "vector-index", maintenance.vector_handler(provider)).acknowledged == (eid,)
    assert indexed(conn, doc, "chunk_embeddings") > 0


def test_poison_event_dead_letters_without_ack_and_requires_operator_replay(connection):
    conn = connection
    _, eid = emit(conn)

    def fail(_conn, _event):
        raise RuntimeError("private details")

    result = maintenance.consume_batch(conn, "lexical-index", fail, max_attempts=1)
    assert result.failed == (eid,) and result.dead_lettered == (eid,)
    assert not maintenance.consume_batch(conn, "lexical-index", fail).failed
    row = conn.execute(
        "select attempts,last_error,dead_lettered_at is not null from outbox_consumer_failures "
        "where consumer='lexical-index' and event_id=%s",
        (eid,),
    ).fetchone()
    assert row == (1, "lexical-index:RuntimeError", True)
    assert conn.execute("select count(*) from outbox_consumer_acks where event_id=%s", (eid,)).fetchone()[0] == 0
    assert outbox.requeue_dead_letter(conn, "lexical-index", eid, actor="operator-01")
    assert maintenance.consume_batch(conn, "lexical-index", lambda _conn, _event: None).acknowledged == (eid,)


def test_one_poison_event_does_not_roll_back_another_success_in_batch(connection):
    conn = connection
    _, first = emit(conn)
    _, second = emit(conn)

    def handler(conn, event):
        if event.event_id == first:
            raise ValueError("bad fixture")

    result = maintenance.consume_batch(conn, "lexical-index", handler)
    assert result.failed == (first,) and result.acknowledged == (second,)
    assert conn.execute("select event_id from outbox_consumer_acks order by event_id").fetchall() == [(second,)]


@pytest.mark.parametrize("status,event_type", [("archived", "document_archived"), ("active", "document_archived")])
def test_current_fact_state_wins_and_archived_indexes_are_kept_for_explicit_history(
    connection, provider, status, event_type
):
    conn = connection
    doc, eid = emit(conn, status=status, event_type=event_type)
    for name, handler in (
        ("lexical-index", maintenance.lexical_handler()),
        ("vector-index", maintenance.vector_handler(provider)),
    ):
        assert maintenance.consume_batch(conn, name, handler).acknowledged == (eid,)
    assert lexical_indexed(conn, doc) > 0 and indexed(conn, doc, "chunk_embeddings") > 0


def test_draft_withdrawal_removes_indexes(connection, provider):
    conn = connection
    doc, eid = emit(conn, status="draft", event_type="document_withdrawn")
    pg_vector.build_index(conn, provider, built_by="test", doc_ids=[doc])
    conn.execute("select set_config('medops.actor','test',true)")
    conn.execute("update documents set status='withdrawn' where doc_id=%s", (doc,))
    for name, handler in (
        ("lexical-index", maintenance.lexical_handler()),
        ("vector-index", maintenance.vector_handler(provider)),
    ):
        assert maintenance.consume_batch(conn, name, handler).acknowledged == (eid,)
    assert lexical_indexed(conn, doc) == 0 and indexed(conn, doc, "chunk_embeddings") == 0


@pytest.mark.parametrize("kind", ["lexical", "vector"])
def test_wrong_metadata_fails_without_ack(connection, provider, kind):
    conn = connection
    _, eid = emit(conn)
    if kind == "lexical":
        conn.execute("update lexical_index_meta set tokenizer_version='wrong'")
        consumer, handler = "lexical-index", maintenance.lexical_handler()
    else:
        conn.execute("update embedding_index_meta set model_revision='wrong'")
        consumer, handler = "vector-index", maintenance.vector_handler(provider)
    result = maintenance.consume_batch(conn, consumer, handler)
    assert result.failed == (eid,) and not result.acknowledged


def test_missing_lexical_row_is_repaired_before_ack(connection):
    conn = connection
    doc, eid = emit(conn)
    before = expected_lexical_assignments(conn, doc)
    deleted = 0
    for table in production.PRODUCTION_LEXICAL_TABLES.values():
        deleted += conn.execute(
            f"delete from {table} where chunk_id in (select chunk_id from chunks where doc_id=%s limit 1)",
            (doc,),
        ).rowcount
    assert deleted > 0
    assert maintenance.consume_batch(conn, "lexical-index", maintenance.lexical_handler()).acknowledged == (eid,)
    assert lexical_indexed(conn, doc) == before


def test_acl_event_for_a_draft_does_not_accidentally_index_unpublished_text(connection, provider):
    conn = connection
    doc, eid = emit(conn, status="draft", event_type="document_acl_changed")
    for name, handler in (
        ("lexical-index", maintenance.lexical_handler()),
        ("vector-index", maintenance.vector_handler(provider)),
    ):
        assert maintenance.consume_batch(conn, name, handler).acknowledged == (eid,)
    assert lexical_indexed(conn, doc) == 0 and indexed(conn, doc, "chunk_embeddings") == 0


def test_actual_commit_survives_restart_and_other_worker_skips_locked_event(admin_dsn):
    from tests.integration.lexical_adapter_suite import make_database, seed_candidate
    from tests.integration.test_lexical_production import CUT

    database = make_database(admin_dsn)
    isolated = next(database)
    try:
        seed_candidate(isolated, CUT)
        with psycopg.connect(isolated["users"]["admin"]) as conn:
            _, eid = emit(conn)
            conn.commit()
        with (
            psycopg.connect(isolated["users"]["admin"]) as first,
            psycopg.connect(isolated["users"]["admin"]) as second,
        ):
            # Explicit outer transaction keeps the event lock/ACK uncommitted while the other worker polls.
            first.execute("select 1")
            assert maintenance.consume_batch(first, "lexical-index", maintenance.lexical_handler()).acknowledged == (
                eid,
            )
            assert not maintenance.consume_batch(second, "lexical-index", maintenance.lexical_handler()).acknowledged
            first.commit()
        with psycopg.connect(isolated["users"]["admin"]) as restarted:
            assert not maintenance.consume_batch(restarted, "lexical-index", maintenance.lexical_handler()).acknowledged
            assert (
                restarted.execute(
                    "select count(*) from outbox_consumer_acks where consumer='lexical-index' and event_id=%s", (eid,)
                ).fetchone()[0]
                == 1
            )
    finally:
        next(database, None)
