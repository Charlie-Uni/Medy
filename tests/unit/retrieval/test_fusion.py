import pytest

from medops.retrieval.fusion import rrf_fuse


def test_rrf_scores_use_ranks_only_and_sum_across_sources():
    fused = rrf_fuse({"lexical": ["a", "b"], "vector": ["b", "c"]}, k=60)
    by_id = {f.chunk_id: f for f in fused}
    assert fused[0].chunk_id == "b" and {r.source: r.rank for r in by_id["b"].source_ranks} == {
        "lexical": 2,
        "vector": 1,
    }
    assert by_id["b"].rrf_score == pytest.approx(1 / 62 + 1 / 61)
    assert by_id["a"].rrf_score == pytest.approx(1 / 61) and by_id["c"].rrf_score == pytest.approx(1 / 62)


def test_rrf_tie_break_and_limit():
    fused = rrf_fuse({"lexical": ["z", "y"], "vector": ["y", "z"]}, limit=1)
    assert [f.chunk_id for f in fused] == ["y"]
    assert [f.rank for f in rrf_fuse({"only": ["q", "p"]})] == [1, 2]


def test_rrf_rejects_duplicates_and_bad_k():
    with pytest.raises(ValueError):
        rrf_fuse({"lexical": ["a", "a"]})
    with pytest.raises(ValueError):
        rrf_fuse({"lexical": ["a"]}, k=0)


def test_fuse_queries_fuses_per_query_rankings_and_keeps_single_query_order():
    from medops.retrieval.hybrid import fuse_queries

    one = fuse_queries([["a", "b", "c"]], k=60.0, limit=20)
    assert [c.chunk_id for c in one] == ["a", "b", "c"] and one[0].source_ranks[0].source == "q1"
    two = fuse_queries([["a", "b", "c"], ["c", "d"]], k=60.0, limit=3)
    assert [c.chunk_id for c in two] == ["c", "a", "b"]  # c is ranked by both queries
    assert {s.source for s in two[0].source_ranks} == {"q1", "q2"}
    assert fuse_queries([[], []], k=60.0, limit=5) == []
