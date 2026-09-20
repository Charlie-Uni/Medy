"""M1-17 hybrid: both channels go through their boundaries, fusion is rank-only RRF with a deterministic
tie-break and the configured cap, and the configuration validates its bounds."""

from __future__ import annotations

import pytest

from medops.core.errors import BusinessError
from medops.retrieval.contracts import LexicalCandidate, LexicalSearchResult, LexicalVersions
from medops.retrieval.hybrid import HybridConfig, hybrid_search
from medops.retrieval.vector.contracts import VectorSearchResult, VectorVersions

LV = LexicalVersions(
    retriever_version="lx", tokenizer_version="t", dictionary_version="d", normalization_version="norm-v1"
)
VV = VectorVersions(retriever_version="vx", embedding_version="e", normalization_version="norm-v1")


def lex(ids, k):
    cands = tuple(LexicalCandidate(chunk_id=c, raw_score=float(len(ids) - i), rank=i + 1) for i, c in enumerate(ids))
    return LexicalSearchResult(
        candidates=cands, requested_k=k, returned_count=len(ids), candidate_exhausted=len(ids) < k, **LV.model_dump()
    )


def vec(ids, k):
    cands = tuple(LexicalCandidate(chunk_id=c, raw_score=1.0 - i * 0.01, rank=i + 1) for i, c in enumerate(ids))
    return VectorSearchResult(
        candidates=cands, requested_k=k, returned_count=len(ids), candidate_exhausted=len(ids) < k, **VV.model_dump()
    )


class FakeLexical:
    versions = LV

    def __init__(self, ids):
        self.ids = ids

    def search(self, query, k):
        return lex(self.ids[:k], k)


class FakeVector:
    versions = VV

    def __init__(self, ids):
        self.ids = ids

    def search(self, query, k):
        return vec(self.ids[:k], k)


def test_fusion_is_rank_only_rrf_with_cap_and_source_ranks():
    cfg = HybridConfig(k_lexical=3, k_vector=3, rrf_k=60.0, limit=4)
    result = hybrid_search(
        FakeLexical(["a", "b", "c"]),
        FakeVector(["c", "d", "a"]),
        "q",
        config=cfg,
        lexical_expected=LV,
        vector_expected=VV,
    )
    assert result.fused_ids[:2] == ["a", "c"]  # both channels; a: 1/61+1/63 > c: 1/63+1/61 equal -> tie by id
    assert len(result.fused) == 4 and result.fused[0].rank == 1
    refs = result.candidate_refs
    assert {s.source for s in refs[0].source_ranks} == {"lexical", "vector"}
    assert result.lexical.requested_k == 3 and result.vector.requested_k == 3


def test_channel_version_mismatch_is_refused_by_the_boundaries():
    cfg = HybridConfig()
    with pytest.raises(BusinessError):
        hybrid_search(
            FakeLexical(["a"]),
            FakeVector(["a"]),
            "q",
            config=cfg,
            lexical_expected=LV.model_copy(update={"tokenizer_version": "x"}),
            vector_expected=VV,
        )
    with pytest.raises(BusinessError):
        hybrid_search(
            FakeLexical(["a"]),
            FakeVector(["a"]),
            "q",
            config=cfg,
            lexical_expected=LV,
            vector_expected=VV.model_copy(update={"embedding_version": "x"}),
        )


def test_config_bounds_and_version_inputs():
    cfg = HybridConfig()
    assert cfg.rrf_params() == {"k": 60.0, "method": "rrf-rank-only"}
    assert cfg.candidate_limits() == {"lexical_k": 20, "vector_k": 20, "fused_limit": 20}
    for bad in ({"k_lexical": 0}, {"k_vector": 21}, {"limit": 0}, {"rrf_k": 0}):
        with pytest.raises(ValueError):
            HybridConfig(**bad)
