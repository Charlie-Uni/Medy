"""ADR-0002 candidate C (pg_search BM25, release_blocked) on its own server: shared suite plus C-specific
identity and tokenizer checks. Skipped unless DEC001_C_ADMIN_URL (.env.dec001) or MEDOPS_TEST_C_ADMIN_URL
points at a reachable server built from builds/c (pg_search 0.25.9, shared_preload_libraries=pg_search)."""

from __future__ import annotations

import json
from collections.abc import Iterator

import psycopg
import pytest

from medops.retrieval.lexical import pg_search_bm25 as c
from tests.integration.lexical_adapter_suite import (
    AS_OF,
    CandidateUnderTest,
    LexicalAdapterSuite,
    make_database,
    require_server,
    seed_candidate,
    txn,
)

OTHER_DICT = "jieba-rs-0.10.1+tantivy-jieba-0.20.0+pg_search.so:0000000000000000"
CUT = CandidateUnderTest(
    name="C",
    index_table=c.INDEX_TABLE,
    install=c.install,
    build=lambda conn, built_by: c.build_index(conn, built_by=built_by),
    make_retriever=lambda conn, as_of: c.PgSearchBm25Retriever(conn, as_of=as_of),
    expected_versions=lambda conn: c.configured_versions(conn),
    make_drifted_retriever=lambda conn, as_of, tmp: c.PgSearchBm25Retriever(
        conn, as_of=as_of, dictionary_version=OTHER_DICT
    ),
    drifted_versions=lambda conn, tmp: c.configured_versions(conn, dictionary_version=OTHER_DICT),
    index_plan_markers=("ParadeDB", c.BM25_INDEX),
)


@pytest.fixture(scope="module")
def server() -> str:
    return require_server("C")


@pytest.fixture(scope="module")
def db(server: str) -> Iterator[dict]:
    yield from make_database(server)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestCandidateC(LexicalAdapterSuite):
    cut = CUT


def test_install_pins_extension_version_and_binary_bytes(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        assert c._extension_version(conn) == "0.25.9"
        assert conn.execute("select extversion from pg_extension where extname = 'vector'").fetchone() == ("0.8.6",)
        c.verify_extension_binary(conn)
        with pytest.raises(c.InstallError):
            c.verify_extension_binary(conn, "00" * 32)
        conn.rollback()
        fields = {r[0] for r in conn.execute(f"select name from paradedb.schema('{c.BM25_INDEX}')")}
        assert {"chunk_id", "content"} <= fields


def test_query_terms_drop_whitespace_and_punctuation_tokens_and_normalize_first(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        assert c.query_terms(conn, "alpha gamma") == ["alpha", "gamma"]  # default jieba keeps ' ' as a token
        assert c.query_terms(conn, "PROT-2024-017") == ["prot-2024", "017"]  # identifier split, '-' dropped
        assert c.query_terms(conn, "研究。") == ["研究"]
        assert c.query_terms(conn, "   ") == [] and c.query_terms(conn, "。、-") == []
        assert c.query_terms(conn, "３０ mg") == ["30", "mg"]


def test_tokenizer_version_reflects_live_extension_and_fixed_config(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        version = c.runtime_tokenizer_version(conn)
        assert version.startswith("pg_search-0.25.9+pdb.jieba:")
        assert c.configured_versions(conn).dictionary_version == c.DICTIONARY_VERSION
        assert c.RELEASE_STATUS == "release_blocked"


def test_plan_uses_the_paradedb_custom_scan_with_the_rls_chain(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        plan = c.PgSearchBm25Retriever(conn, as_of=AS_OF).explain("sigma 研究", 20)
    tree = json.loads(plan)
    assert tree[0]["Plan"]["Node Type"] == "Limit"
    assert "ParadeDB" in plan and c.BM25_INDEX in plan
    assert "document_acl" in plan and "current_setting('medops.dept'" in plan


def test_multiword_or_does_not_match_on_whitespace(db, seed):
    """The pre-run rule: 'sigma 随访' must match chunks containing sigma or 随访, not every chunk with a space."""
    with txn(db["users"]["app"], "MA") as conn:
        r = c.PgSearchBm25Retriever(conn, as_of=AS_OF).search("sigma 随访", 20)
    assert r.returned_count == 4 and r.candidate_exhausted is True
