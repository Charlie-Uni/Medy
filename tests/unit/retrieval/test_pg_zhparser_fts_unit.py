"""Candidate B constants and pure rules that need no database (the server-bound behaviour is covered in
tests/integration/test_lexical_pg_zhparser_fts.py when a candidate B server is configured)."""

from __future__ import annotations

from medops.retrieval.lexical import pg_zhparser_fts as b


def test_fixed_mapping_keeps_every_pos_type_except_w():
    assert len(b.MAPPED_TOKEN_TYPES) == 25 and "w" not in b.MAPPED_TOKEN_TYPES
    assert "".join(sorted(b.MAPPED_TOKEN_TYPES)) == "abcdefghijklmnopqrstuvxyz"


def test_dictionary_version_is_derived_from_the_pinned_file_hashes_and_scws_version():
    hashes = list(b.DICTIONARY_FILES.values())
    assert all(len(h) == 64 for h in hashes) and len(set(hashes)) == 2
    assert b.DICTIONARY_VERSION == f"scws-dict-utf8:{hashes[0][:16]}+rules-utf8:{hashes[1][:16]}+scws-{b.SCWS_VERSION}"
    assert b.EXPECTED_EXTENSION_VERSION == "2.3" and b.SCWS_VERSION == "1.2.3"


def test_install_and_search_sql_target_the_candidate_b_table():
    assert "lexical_index_b" in b.INSTALL_SQL and "lexical_index_meta" in b.INSTALL_SQL
    assert b.SEARCH_SQL.count("lexical_index_b") == 1 and "count(*) over ()" in b.SEARCH_SQL
    assert b.RETRIEVER_VERSION == "pg-zhparser-fts-v1" and b.TS_CONFIG == "dec001_b"


def test_punctuation_only_rule_matches_symbol_lexemes_but_not_words_or_numbers():
    assert all(b._PUNCT_ONLY.match(t) for t in ["。", ".", "-", "/", "、", "_", "!!!"])
    assert not any(b._PUNCT_ONLY.match(t) for t in ["研究", "mg", "30", "prot", "12.5"])
