"""M1-14: the production lexical index (migration 0007 table, pinned tokenizer and stopwords) passes the same
adapter suite as the DEC-001 candidates: zero leakage including counts, no silent shortfall, status/window
filtering inside the query, identity and version refusals, plan evidence and write protection."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from medops.retrieval import production
from medops.retrieval.lexical import pg_simple_fts as a
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
    index_table=production.PRODUCTION_LEXICAL_TABLE,
    install=lambda conn: None,  # migration 0007 creates the tables
    build=lambda conn, built_by: production.build_production_lexical_index(conn, built_by=built_by),
    make_retriever=lambda conn, as_of: production.production_lexical_retriever(conn, as_of=as_of),
    expected_versions=lambda conn: production.production_lexical_versions(),
    make_drifted_retriever=lambda conn, as_of, tmp: a.PgSimpleFtsRetriever(
        conn,
        DRIFTED,
        as_of=as_of,
        index_name=production.PRODUCTION_LEXICAL_INDEX_NAME,
        table=production.PRODUCTION_LEXICAL_TABLE,
    ),
    drifted_versions=lambda conn, tmp: a.configured_versions(DRIFTED),
    index_plan_markers=(f"{production.PRODUCTION_LEXICAL_TABLE}_tsv_gin", "Bitmap"),
)


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestProductionLexical(LexicalAdapterSuite):
    cut = CUT


def test_production_index_target_keeps_the_table_in_step(db, seed):
    target = production.production_index_target()
    assert target.name == production.PRODUCTION_LEXICAL_TABLE
    with psycopg.connect(db["owner"]) as conn:
        doc = conn.execute("select doc_id from documents where status = 'active' limit 1").fetchone()[0]
        before = conn.execute(f"select count(*) from {production.PRODUCTION_LEXICAL_TABLE}").fetchone()[0]
        removed = target.remove(conn, doc)
        assert removed > 0
        assert target.add(conn, doc) == removed
        assert conn.execute(f"select count(*) from {production.PRODUCTION_LEXICAL_TABLE}").fetchone()[0] == before
        conn.rollback()


def test_stopwords_are_the_pinned_vendored_file():
    path = production.stopwords_path()
    assert path.is_file() and path.name == "english.stop" and "medops/retrieval/lexical/resources" in str(Path(path))
