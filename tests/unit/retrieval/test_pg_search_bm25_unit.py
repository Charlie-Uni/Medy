"""Candidate C constants and SQL shape without a database."""

from __future__ import annotations

from medops.retrieval.lexical import pg_search_bm25 as c


def test_fixed_tokenizer_configuration_matches_the_build_smoke():
    assert c.TOKENIZER_SQL == "pdb.jieba('lowercase=true', 'ascii_folding=false', 'alpha_num_only=false', 'trim=false')"
    assert c.TOKENIZER_SQL in c.INSTALL_SQL and c.TOKENIZER_SQL in c.SEARCH_SQL
    assert c.EXPECTED_EXTENSION_VERSION == "0.25.9" and c.RELEASE_STATUS == "release_blocked"


def test_dictionary_version_pins_the_extension_binary_hash():
    assert len(c.EXTENSION_BINARY_SHA256) == 64
    assert c.DICTIONARY_VERSION.endswith(c.EXTENSION_BINARY_SHA256[:16])


def test_search_sql_is_one_count_and_page_statement_over_an_array_or_predicate():
    sql = c.SEARCH_SQL
    assert "||| %(terms)s::text[]" in sql and "paradedb.score(i.chunk_id)" in sql
    assert "count(*) over ()" in sql and "d.status = 'active'" in sql and "limit %(k)s" in sql
    assert "order by score desc, chunk_id asc" in sql


def test_whitespace_and_punctuation_rule():
    assert all(c._PUNCT_OR_SPACE_ONLY.match(t) for t in [" ", "。", "-", "/", "_", "  "])
    assert not any(c._PUNCT_OR_SPACE_ONLY.match(t) for t in ["研究", "mg", "30", "prot-2024", "12.5"])
