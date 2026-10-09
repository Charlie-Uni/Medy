"""Index coverage (record 109): active documents whose chunks are missing from the lexical index or the embeddings are
invisible to retrieval, so every measurement must refuse to run until both indexes cover every active chunk."""

from __future__ import annotations

import pytest

from medops.retrieval.production import IndexCoverageError, index_coverage, require_index_coverage


class _Conn:
    def __init__(self, row):
        self._row = row
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params
        return self

    def fetchone(self):
        return self._row


def test_coverage_counts_only_active_documents_for_the_production_embedding_version():
    conn = _Conn((34948, 0, 0, 0))
    assert index_coverage(conn) == {
        "active_chunks": 34948,
        "missing_lexical": 0,
        "missing_embedding": 0,
        "documents_not_fully_indexed": 0,
    }
    assert "d.status='active'" in conn.sql and "chunk_lexical_bm25_ma" in conn.sql and "chunk_embeddings" in conn.sql
    assert conn.params == ("emb-bge-m3-dense-v1",)


def test_measurements_refuse_a_plane_with_unindexed_active_documents():
    # the state found on 2026-10-02: 257 active documents, 24,599 chunks, in neither index
    with pytest.raises(IndexCoverageError, match="257 active documents are not fully indexed"):
        require_index_coverage(_Conn((34948, 24599, 24599, 257)), plane="medops_v2")
    with pytest.raises(IndexCoverageError):
        require_index_coverage(_Conn((100, 0, 3, 1)))  # embeddings alone missing is enough to refuse
    assert require_index_coverage(_Conn((100, 0, 0, 0)))["active_chunks"] == 100
