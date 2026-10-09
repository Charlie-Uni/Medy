"""Production departmental BM25 (migration 0022) passes the shared lexical contract and proves that both rows
and BM25 corpus statistics stay inside the MA/PV/CO boundary."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from medops.retrieval import production
from medops.retrieval.lexical import pg_textsearch_departmental as bm25
from tests.integration.lexical_adapter_suite import (
    CandidateUnderTest,
    LexicalAdapterSuite,
    make_database,
    seed_candidate,
)

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

DRIFTED = JiebaTokenizerV1()

CUT = CandidateUnderTest(
    name="production",
    index_table=production.PRODUCTION_LEXICAL_TABLES["MA"],
    install=lambda conn: None,  # migration 0022 creates the extension, tables and BM25 indexes
    build=lambda conn, built_by: production.build_production_lexical_index(conn, built_by=built_by),
    make_retriever=lambda conn, as_of: production.production_lexical_retriever(conn, as_of=as_of),
    expected_versions=lambda conn: production.production_lexical_versions(),
    make_drifted_retriever=lambda conn, as_of, tmp: bm25.DepartmentalBm25Retriever(conn, DRIFTED, as_of=as_of),
    drifted_versions=lambda conn, tmp: bm25.configured_versions(DRIFTED),
    index_plan_markers=tuple(bm25.INDEXES.values()),
)


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestProductionLexical(LexicalAdapterSuite):
    cut = CUT

    def test_build_indexes_every_chunk_and_records_the_versions(self, db, seed):
        """Production BM25 excludes draft/withdrawn text from both rows and corpus statistics."""
        report = seed["report"]
        with psycopg.connect(db["owner"]) as conn:
            published = conn.execute(
                "select count(*) from chunks c join documents d using(doc_id) where d.status in ('active','archived')"
            ).fetchone()[0]
        assert report.chunk_count == published and report.skipped_empty == 0
        with psycopg.connect(db["users"]["app"]) as conn:
            with conn.transaction():
                conn.execute("select set_config('medops.dept','MA',true)")
                expected = self.cut.expected_versions(conn)
                assert report.versions == expected
                assert self.cut.make_retriever(conn, None).versions == expected

    def test_install_is_idempotent_and_tables_are_force_rls_with_least_grants(self, db, seed):
        with psycopg.connect(db["owner"]) as conn:
            assert bm25.extension_version(conn) == bm25.EXPECTED_EXTENSION_VERSION
            for table in production.PRODUCTION_LEXICAL_TABLES.values():
                rls = conn.execute(
                    "select relrowsecurity, relforcerowsecurity from pg_class where relname=%s", (table,)
                ).fetchone()
                assert rls == (True, True)
                grants = {
                    (r[0], r[1])
                    for r in conn.execute(
                        "select grantee, privilege_type from information_schema.role_table_grants where table_name=%s",
                        (table,),
                    )
                }
                for role in ("medops_app", "medops_readonly"):
                    assert {p for g, p in grants if g == role} == {"SELECT"}
                assert {p for g, p in grants if g == "medops_admin_role"} == {
                    "SELECT",
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                }
            unique = conn.execute(
                "select count(distinct chunk_id) from ("
                + " union all ".join(f"select chunk_id from {t}" for t in production.PRODUCTION_LEXICAL_TABLES.values())
                + ") indexed"
            ).fetchone()[0]
            assert unique == seed["report"].chunk_count


def test_production_index_target_keeps_the_table_in_step(db, seed):
    target = production.production_index_target()
    assert target.name == "departmental-bm25"
    with psycopg.connect(db["owner"]) as conn:
        doc = conn.execute(
            "select d.doc_id from documents d join document_acl a using(doc_id) "
            "where d.status='active' group by d.doc_id having count(*) > 1 limit 1"
        ).fetchone()[0]
        before = sum(
            conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in production.PRODUCTION_LEXICAL_TABLES.values()
        )
        removed = target.remove(conn, doc)
        assert removed > 0
        assert target.add(conn, doc) == removed
        after = sum(
            conn.execute(f"select count(*) from {table}").fetchone()[0]
            for table in production.PRODUCTION_LEXICAL_TABLES.values()
        )
        assert after == before
        conn.rollback()


def test_department_corpora_and_scores_are_isolated(db, seed):
    """Adding a known term to MA changes MA's corpus only; PV's BM25 score is byte-for-byte stable."""
    from tests.integration.lexical_adapter_suite import AS_OF, txn
    from tests.integration.test_migrations import document, job, source_object

    with txn(db["users"]["app"], "PV") as conn:
        before = production.production_lexical_retriever(conn, as_of=AS_OF).search("sigma", 20)
        before_scores = [(c.chunk_id, c.raw_score) for c in before.candidates]
    with psycopg.connect(db["owner"]) as conn:
        src = source_object(conn, 999991)
        doc = document(
            conn,
            src,
            job(conn, src),
            owner_dept="MA",
            status="active",
            effective_from=AS_OF,
            version="stats-isolation",
        )
        conn.execute("insert into document_acl values (%s, 'MA', 'read', 'test', now())", (doc,))
        for seq in range(40):
            conn.execute(
                "insert into chunks (doc_id,seq,page,content,chunk_content_hash) values (%s,%s,1,%s,null)",
                (doc, seq, f"sigma ma-only-frequency-{seq}"),
            )
        target = production.production_index_target()
        assert target.add(conn, doc) == 40
        conn.commit()
    with txn(db["users"]["app"], "PV") as conn:
        after = production.production_lexical_retriever(conn, as_of=AS_OF).search("sigma", 20)
        assert [(c.chunk_id, c.raw_score) for c in after.candidates] == before_scores
        assert conn.execute("select count(*) from chunk_lexical_bm25_ma").fetchone()[0] == 0


def test_acl_revoke_removes_bm25_statistics_in_the_same_transaction(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        doc = conn.execute(
            "select d.doc_id from documents d join document_acl a using(doc_id) "
            "where d.status='active' group by d.doc_id having count(*) > 1 limit 1"
        ).fetchone()[0]
        pv_before = conn.execute(
            "select count(*) from chunk_lexical_bm25_pv i join chunks c using(chunk_id) where c.doc_id=%s", (doc,)
        ).fetchone()[0]
        assert pv_before > 0
        conn.execute("delete from document_acl where doc_id=%s and dept='PV' and permission='read'", (doc,))
        assert (
            conn.execute(
                "select count(*) from chunk_lexical_bm25_pv i join chunks c using(chunk_id) where c.doc_id=%s", (doc,)
            ).fetchone()[0]
            == 0
        )
        conn.rollback()


def test_stopwords_are_the_pinned_vendored_file():
    path = production.stopwords_path()
    assert path.is_file() and path.name == "english.stop" and "medops/retrieval/lexical/resources" in str(Path(path))
