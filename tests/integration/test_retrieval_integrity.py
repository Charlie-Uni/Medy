"""Real index loss, metadata drift and outbox state must be visible before serving traffic."""

from datetime import date

import psycopg
import pytest

from medops.ingestion import outbox
from medops.retrieval.integrity import inspect_retrieval, require_retrieval_integrity
from medops.retrieval.production import IndexCoverageError
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.embedding import EMBEDDING_VERSION, HashingEmbeddingProvider
from tests.integration.test_lexical_production import db as db  # noqa: F401
from tests.integration.test_lexical_production import seed as seed  # noqa: F401
from tests.integration.test_migrations import document, job, source_object


@pytest.fixture(scope="module")
def indexed(db, seed):
    provider = HashingEmbeddingProvider(embedding_version=EMBEDDING_VERSION)
    with psycopg.connect(db["owner"]) as conn:
        pg_vector.build_index(conn, provider, built_by="test-only-synthetic-vectors")
        conn.commit()
    return provider.spec


def test_complete_indexes_report_ready_under_read_only_transaction(db, indexed):
    with psycopg.connect(db["owner"]) as conn:
        conn.read_only = True
        status = require_retrieval_integrity(conn, embedding=indexed, plane="fixture", request_conn=conn)
    assert status["ready"] and status["coverage"]["active_chunks"] > 0
    assert not status["problems"] and status["lexical_version_ok"] and status["embedding_version_ok"]


@pytest.mark.parametrize(
    "fault,reason",
    [
        ("lexical", "lexical_coverage_gap"),
        ("embedding", "embedding_coverage_gap"),
        ("tokenizer", "lexical_version_missing_or_mismatched"),
        ("model", "embedding_version_missing_or_mismatched"),
        ("empty_document", "active_document_without_chunks"),
    ],
)
def test_real_storage_faults_make_index_health_false(db, indexed, fault, reason):
    with psycopg.connect(db["owner"]) as conn:
        cid = conn.execute(
            "select c.chunk_id from chunks c join documents d on c.doc_id=d.doc_id where d.status='active' limit 1"
        ).fetchone()[0]
        if fault == "lexical":
            for table in ("chunk_lexical_bm25_ma", "chunk_lexical_bm25_pv", "chunk_lexical_bm25_co"):
                conn.execute(f"delete from {table} where chunk_id=%s", (cid,))
        elif fault == "embedding":
            conn.execute("delete from chunk_embeddings where chunk_id=%s", (cid,))
        elif fault == "tokenizer":
            conn.execute(
                "update lexical_index_meta set tokenizer_version='wrong' where index_name='production-lexical'"
            )
        elif fault == "model":
            conn.execute(
                "update embedding_index_meta set model_revision='wrong' where embedding_version=%s",
                (EMBEDDING_VERSION,),
            )
        else:
            src = source_object(conn, 990001)
            document(conn, src, job(conn, src), status="active", effective_from=date(2026, 1, 1))
        status = inspect_retrieval(conn, embedding=indexed)
        assert not status["ready"] and reason in status["problems"]
        with pytest.raises(IndexCoverageError, match=reason):
            require_retrieval_integrity(conn, embedding=indexed, plane="fixture")
        conn.rollback()


def test_rls_empty_view_cannot_be_mistaken_for_complete_global_indexes(db, indexed):
    with psycopg.connect(db["users"]["app"]) as conn:
        with pytest.raises(ValueError, match="administrative visibility"):
            inspect_retrieval(conn, embedding=indexed)


def test_outbox_uses_per_consumer_acks_even_when_published_flag_is_set(db, indexed):
    with psycopg.connect(db["owner"]) as conn:
        before = inspect_retrieval(conn, embedding=indexed)
        doc, family = conn.execute("select doc_id, family_id from documents where status='active' limit 1").fetchone()
        eid = outbox.emit(
            conn,
            "document_acl_changed",
            aggregate_id=doc,
            family_id=family,
            payload={"acl_depts": ["MA"]},
            actor="test",
        )
        conn.execute("update outbox_events set published_at=now() where event_id=%s", (eid,))
        pending = inspect_retrieval(conn, embedding=indexed)
        for consumer in ("lexical-index", "retrieval-cache"):
            assert pending["outbox"][consumer]["pending"] == before["outbox"][consumer]["pending"] + 1
        outbox.ack(conn, "lexical-index", eid)
        after = inspect_retrieval(conn, embedding=indexed)
        assert after["outbox"]["lexical-index"]["pending"] == before["outbox"]["lexical-index"]["pending"]
        assert after["outbox"]["retrieval-cache"]["pending"] == pending["outbox"]["retrieval-cache"]["pending"]
        assert after["ready"] and after["outbox_blocks_readiness"] is False
        conn.rollback()


def test_stale_optional_cache_backlog_is_visible_but_does_not_block_index_readiness(db, indexed):
    with psycopg.connect(db["owner"]) as conn:
        doc, family = conn.execute("select doc_id, family_id from documents where status='active' limit 1").fetchone()
        eid = conn.execute(
            "insert into outbox_events(event_type,aggregate_id,family_id,payload,created_by,created_at) "
            "values ('document_acl_changed',%s,%s,'{\"acl_depts\":[\"MA\"]}'::jsonb,'test',"
            "now()-interval '1 hour') returning event_id",
            (doc, family),
        ).fetchone()[0]
        outbox.ack(conn, "lexical-index", eid)
        outbox.ack(conn, "vector-index", eid)
        status = inspect_retrieval(conn, embedding=indexed)
        assert status["outbox"]["retrieval-cache"]["oldest_age_s"] >= 3600
        assert status["ready"] and status["outbox_blocks_readiness"] is False
        conn.rollback()


def test_empty_migrated_database_cannot_report_ready(scratch_database):
    from tests.integration.conftest import run_alembic

    run_alembic(scratch_database, "upgrade", "head")
    with psycopg.connect(scratch_database) as conn:
        conn.read_only = True
        status = inspect_retrieval(conn)
    assert not status["ready"] and "empty_active_corpus" in status["problems"]
    assert not status["lexical_version_ok"] and not status["embedding_version_ok"]
