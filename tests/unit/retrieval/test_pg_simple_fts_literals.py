"""Candidate A literal builders: the tokenizer's tokens must survive the trip into tsvector/tsquery text
unchanged (quotes, backslashes, CJK, identifiers), positions must be preserved and server limits applied
client-side so what we send is what PostgreSQL stores. Database behaviour is covered in
tests/integration/test_lexical_pg_simple_fts.py."""

from __future__ import annotations

import pytest

from medops.retrieval.lexical import pg_simple_fts as a
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1


def test_tsvector_literal_preserves_positions_and_first_occurrence_order():
    assert a.tsvector_literal(["alpha", "beta", "alpha"]) == "'alpha':1,3 'beta':2"
    assert a.tsvector_literal([]) == ""


def test_lexeme_quoting_doubles_quotes_and_backslashes():
    assert a.tsvector_literal(["it's"]) == "'it''s':1"
    assert a.tsvector_literal(["a\\b"]) == "'a\\\\b':1"
    assert a.tsquery_literal(["it's", "a\\b"]) == "'it''s' | 'a\\\\b'"


def test_cjk_and_identifier_tokens_are_quoted_verbatim():
    assert a.tsvector_literal(["美洛醣", "prot-2024-017", "30"]) == "'美洛醣':1 'prot-2024-017':2 '30':3"


def test_tsquery_is_or_over_distinct_tokens():
    assert a.tsquery_literal(["x", "y", "x"]) == "'x' | 'y'"
    with pytest.raises(ValueError):
        a.tsquery_literal([])


def test_empty_or_oversized_tokens_are_rejected():
    with pytest.raises(ValueError):
        a.tsvector_literal([""])
    with pytest.raises(ValueError):
        a.tsvector_literal(["x" * (a.MAX_LEXEME_BYTES + 1)])


def test_server_limits_are_applied_client_side():
    many = ["t"] * (a.MAX_POSITIONS_PER_LEXEME + 5)
    literal = a.tsvector_literal(many)
    assert literal.count(",") == a.MAX_POSITIONS_PER_LEXEME - 1
    far = ["pad"] * a.MAX_POSITION + ["end"]
    assert a.tsvector_literal(far).endswith(f"'end':{a.MAX_POSITION}")


def test_configured_versions_come_from_the_tokenizer():
    pytest.importorskip("jieba")
    versions = a.configured_versions(JiebaTokenizerV1())
    assert versions.retriever_version == a.RETRIEVER_VERSION == "pg-simple-fts-v1"
    assert versions.tokenizer_version == "tok-jieba-v1"
    assert versions.dictionary_version.startswith("jieba-") and versions.normalization_version == "norm-v1"


def test_search_sql_counts_and_pages_from_one_statement_with_the_same_filters():
    sql = a.SEARCH_SQL
    assert sql.count("%(q)s::tsquery") == 2 and "count(*) over ()" in sql
    assert "d.status = 'active'" in sql and "effective_from <= %(as_of)s" in sql and "effective_to > %(as_of)s" in sql
    assert "order by score desc, chunk_id asc" in sql and "limit %(k)s" in sql
