"""ADR-0002 candidate D (pg_textsearch BM25, revision 5) on its own PostgreSQL 17 server: the shared adapter suite
(ordinary role + FORCE RLS zero leakage, exact candidate counts without silent shortfall, identity and version
rules, reproducible ranking) plus D-specific checks. Skipped unless DEC001_D_ADMIN_URL (.env.dec001) or
MEDOPS_TEST_D_ADMIN_URL points at a reachable server built from builds/d (shared_preload_libraries=pg_textsearch)."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from medops.retrieval.lexical import pg_textsearch_bm25 as d
from medops.retrieval.production import stopwords_path
from tests.integration.lexical_adapter_suite import (
    AS_OF,
    CandidateUnderTest,
    LexicalAdapterSuite,
    make_database,
    require_server,
    seed_candidate,
    txn,
)

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1, JiebaTokenizerV2  # noqa: E402

TOKENIZER = JiebaTokenizerV2(stopwords=stopwords_path())  # the production tokenizer: D differs from A2 in ranking only
DRIFTED = JiebaTokenizerV1()

CUT = CandidateUnderTest(
    name="D",
    index_table=d.INDEX_TABLE,
    install=d.install,
    build=lambda conn, built_by: d.build_index(conn, TOKENIZER, built_by=built_by),
    make_retriever=lambda conn, as_of: d.PgTextsearchBm25Retriever(conn, TOKENIZER, as_of=as_of),
    expected_versions=lambda conn: d.configured_versions(conn, TOKENIZER),
    make_drifted_retriever=lambda conn, as_of, tmp: d.PgTextsearchBm25Retriever(conn, DRIFTED, as_of=as_of),
    drifted_versions=lambda conn, tmp: d.configured_versions(conn, DRIFTED),
    index_plan_markers=(d.BM25_INDEX,),
)


@pytest.fixture(scope="module")
def server() -> str:
    return require_server("D")


@pytest.fixture(scope="module")
def db(server: str) -> Iterator[dict]:
    yield from make_database(server)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestCandidateD(LexicalAdapterSuite):
    cut = CUT


def test_install_pins_the_extension_version_and_the_index_options(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        assert d._extension_version(conn) == d.EXPECTED_EXTENSION_VERSION
        opts = conn.execute(
            "select array_to_string(reloptions, ',') from pg_class where relname = %s", (d.BM25_INDEX,)
        ).fetchone()
        assert opts and "text_config=simple" in opts[0] and "k1=1.2" in opts[0] and "b=0.75" in opts[0]
        versions = d.configured_versions(conn, TOKENIZER)
        assert versions.retriever_version == "pg-textsearch-bm25-v1"
        assert (
            versions.tokenizer_version.startswith("tok-jieba-v2")
            and "pg_textsearch-1.5.1:simple" in versions.tokenizer_version
        )


def test_scores_are_positive_best_first_and_non_matching_rows_are_absent(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        r = d.PgTextsearchBm25Retriever(conn, TOKENIZER, as_of=AS_OF).search("sigma", 20)
        scores = [c.raw_score for c in r.candidates]
        assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)
        assert 0 < len(r.candidates) <= 20  # rows that match no term are absent (the `< 0` predicate)
