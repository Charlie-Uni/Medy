"""ADR-0002 candidate A on the real schema with real LOGIN users (shared suite + A-specific checks)."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from medops.retrieval.lexical import pg_simple_fts as a
from tests.integration.lexical_adapter_suite import (
    CandidateUnderTest,
    LexicalAdapterSuite,
    make_database,
    seed_candidate,
)

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

TOKENIZER = JiebaTokenizerV1()


def _drifted_tokenizer(tmp_path):
    user_dict = tmp_path / "med.dict"
    user_dict.write_text("美洛醣 10 n\n", encoding="utf-8")
    return JiebaTokenizerV1(user_dictionary=user_dict)


CUT = CandidateUnderTest(
    name="A",
    index_table=a.INDEX_TABLE,
    install=a.install,
    build=lambda conn, built_by: a.build_index(conn, TOKENIZER, built_by=built_by),
    make_retriever=lambda conn, as_of: a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=as_of),
    expected_versions=lambda conn: a.configured_versions(TOKENIZER),
    make_drifted_retriever=lambda conn, as_of, tmp: a.PgSimpleFtsRetriever(conn, _drifted_tokenizer(tmp), as_of=as_of),
    drifted_versions=lambda conn, tmp: a.configured_versions(_drifted_tokenizer(tmp)),
    index_plan_markers=(f"{a.INDEX_TABLE}_tsv_gin", "Bitmap"),
)


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestCandidateA(LexicalAdapterSuite):
    cut = CUT


def test_literals_round_trip_through_postgres(db, seed):
    tokens = ["it's", "a\\b", "美洛醣", "prot-2024-017", "30", "it's"]
    with psycopg.connect(db["owner"]) as conn:
        stored = conn.execute("select tsvector_to_array(%s::tsvector)", (a.tsvector_literal(tokens),)).fetchone()[0]
        assert set(stored) == set(tokens)
        positions = conn.execute("select %s::tsvector::text", (a.tsvector_literal(tokens),)).fetchone()[0]
        assert "'it''s':1,6" in positions
        for token in set(tokens):
            hit = conn.execute(
                "select %s::tsvector @@ %s::tsquery", (a.tsvector_literal(tokens), a.tsquery_literal([token]))
            ).fetchone()[0]
            assert hit is True, token
        assert (
            conn.execute(
                "select %s::tsvector @@ %s::tsquery", (a.tsvector_literal(tokens), a.tsquery_literal(["zzz"]))
            ).fetchone()[0]
            is False
        )
