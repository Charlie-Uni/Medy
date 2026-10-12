"""Interpolated identifiers stay server-selected; queries/doc IDs stay SQL parameters."""

import pytest

from medops.retrieval.lexical.pg_bm25_common import bm25_search_sql


@pytest.mark.parametrize("value", ["bad-name", "x' ); drop table chunks; --", "schema.table", "x;select"])
@pytest.mark.parametrize("argument", ["table", "index"])
def test_bm25_sql_rejects_noncanonical_identifiers(value, argument):
    names = {"table": "chunk_lexical_bm25_pv", "index": "chunk_lexical_bm25_pv_idx"}
    names[argument] = value
    with pytest.raises(ValueError, match="fixed SQL identifier"):
        bm25_search_sql(**names)
