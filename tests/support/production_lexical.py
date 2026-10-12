"""Shared production lexical test support; no collected test cases."""

from __future__ import annotations

import pytest

from medops.retrieval import production
from medops.retrieval.lexical import pg_textsearch_departmental as bm25
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402
from tests.integration.lexical_adapter_suite import CandidateUnderTest, seed_candidate

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
def seed(db: dict) -> dict:
    return seed_candidate(db, CUT)
