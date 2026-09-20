"""ADR-0002 candidate B (zhparser) on its own server: shared suite plus B-specific identity checks.

Skipped unless DEC001_B_ADMIN_URL (.env.dec001) or MEDOPS_TEST_B_ADMIN_URL points at a reachable server
built from builds/b (zhparser 2.3 + SCWS 1.2.3); CI has no such server, local evidence is recorded in
the implementation record."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from medops.retrieval.lexical import pg_zhparser_fts as b
from tests.integration.lexical_adapter_suite import (
    CandidateUnderTest,
    LexicalAdapterSuite,
    make_database,
    require_server,
    seed_candidate,
    txn,
)

CUT = CandidateUnderTest(
    name="B",
    index_table=b.INDEX_TABLE,
    install=b.install,
    build=lambda conn, built_by: b.build_index(conn, built_by=built_by),
    make_retriever=lambda conn, as_of: b.PgZhparserFtsRetriever(conn, as_of=as_of),
    expected_versions=lambda conn: b.configured_versions(conn),
    make_drifted_retriever=lambda conn, as_of, tmp: b.PgZhparserFtsRetriever(
        conn, as_of=as_of, dictionary_version="scws-dict-utf8:0000000000000000+other"
    ),
    drifted_versions=lambda conn, tmp: b.configured_versions(
        conn, dictionary_version="scws-dict-utf8:0000000000000000+other"
    ),
    index_plan_markers=(f"{b.INDEX_TABLE}_tsv_gin", "Bitmap"),
)


@pytest.fixture(scope="module")
def server() -> str:
    return require_server("B")


@pytest.fixture(scope="module")
def db(server: str) -> Iterator[dict]:
    yield from make_database(server)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)


class TestCandidateB(LexicalAdapterSuite):
    cut = CUT


def test_install_pins_extension_configuration_and_dictionary_bytes(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        assert b._extension_version(conn) == "2.3"
        assert b._mapping(conn) == [(t, 1, "simple") for t in b.MAPPED_TOKEN_TYPES]
        assert "w" not in b.MAPPED_TOKEN_TYPES and len(b.MAPPED_TOKEN_TYPES) == 25
        b.verify_dictionary_files(conn)  # the pinned SHA-256 values match the bytes in the image
        with pytest.raises(b.InstallError):
            b.verify_dictionary_files(conn, {next(iter(b.DICTIONARY_FILES)): "00" * 32})
        conn.rollback()


def test_tokenizer_version_reflects_live_extension_mapping_and_gucs(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        version = b.runtime_tokenizer_version(conn)
        assert version.startswith("zhparser-2.3+scws-1.2.3+cfg-dec001_b:") and "+guc:" in version
        assert b.configured_versions(conn).dictionary_version == b.DICTIONARY_VERSION


def test_query_tokens_drop_punctuation_only_lexemes_and_normalize_first(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        assert b.query_tokens(conn, "研究。") == ["研究"]
        assert b.query_tokens(conn, "PROT-2024-017") == ["017", "2024", "prot"]  # zhparser splits identifiers
        assert b.query_tokens(conn, "   ") == [] and b.query_tokens(conn, "。、-") == []
        # full-width digits are norm-v1 mapped before tokenizing
        assert b.query_tokens(conn, "３０ mg") == ["30", "mg"]


def test_traditional_chinese_is_split_per_character_by_the_scws_dictionary(db, seed):
    """Characterization, not a quality claim: the fixed SCWS dictionary has no Traditional entries, so
    zh-Hant clauses tokenize per character. Recorded as a known property of candidate B before the run."""
    with txn(db["users"]["app"], "MA") as conn:
        assert set(b.query_tokens(conn, "觀察時間")) == set("觀察時間")
        assert b.query_tokens(conn, "观察时间") == ["时间", "观察"]


# --- variant B2 (ADR-0002 amendment 2): dec001_b2 with the simple dictionary + English stopwords, own table
CUT_B2 = CandidateUnderTest(
    name="B2",
    index_table=b.VARIANT_B2.table,
    install=lambda conn: b.install(conn, b.VARIANT_B2),
    build=lambda conn, built_by: b.build_index(conn, built_by=built_by, variant=b.VARIANT_B2),
    make_retriever=lambda conn, as_of: b.PgZhparserFtsRetriever(conn, as_of=as_of, variant=b.VARIANT_B2),
    expected_versions=lambda conn: b.configured_versions(
        conn, dictionary_version=b.VARIANT_B2.dictionary_version, variant=b.VARIANT_B2
    ),
    make_drifted_retriever=lambda conn, as_of, tmp: b.PgZhparserFtsRetriever(
        conn, as_of=as_of, variant=b.VARIANT_B2, dictionary_version="scws-dict-utf8:0000000000000000+other"
    ),
    drifted_versions=lambda conn, tmp: b.configured_versions(
        conn, dictionary_version="scws-dict-utf8:0000000000000000+other", variant=b.VARIANT_B2
    ),
    index_plan_markers=(f"{b.VARIANT_B2.table}_tsv_gin", "Bitmap"),
)


@pytest.fixture(scope="module")
def db_b2(server: str) -> Iterator[dict]:
    yield from make_database(server)


@pytest.fixture(scope="module")
def seed_b2(db_b2: dict) -> dict:
    return seed_candidate(db_b2, CUT_B2)


class TestCandidateB2(LexicalAdapterSuite):
    cut = CUT_B2

    @pytest.fixture
    def db(self, db_b2):
        return db_b2

    @pytest.fixture
    def seed(self, seed_b2):
        return seed_b2


def test_b2_drops_english_stopwords_on_index_and_query_side(db_b2, seed_b2):
    with psycopg.connect(db_b2["owner"]) as owner:
        b.install(owner, b.VARIANT_B)  # the plain configuration, for a side-by-side comparison
        owner.commit()
    with txn(db_b2["users"]["app"], "MA") as conn:
        assert b.query_tokens(conn, "what are the minimum elements", b.VARIANT_B2.ts_config) == ["elements", "minimum"]
        assert "the" in b.query_tokens(conn, "what are the minimum elements", b.VARIANT_B.ts_config)
        versions = b.configured_versions(conn, dictionary_version=b.VARIANT_B2.dictionary_version, variant=b.VARIANT_B2)
        assert "cfg-dec001_b2:" in versions.tokenizer_version
        assert versions.dictionary_version.endswith("+stop-english:" + b.STOPWORD_SHA256[:16])
