"""M1-16 vector contracts, the hashing test provider and the vector boundary (no database)."""

from __future__ import annotations

import math

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.contracts import Candidate, VectorSearchResult, VectorVersions
from medops.retrieval.vector.embedding import DIMENSION, HashingEmbeddingProvider
from medops.retrieval.vector.pg_vector import vector_literal

V = VectorVersions(
    retriever_version="pgvector-hnsw-cosine-v1", embedding_version="emb-hash-test-v1", normalization_version="norm-v1"
)


def result(*scores: tuple[str, float], k: int = 5) -> VectorSearchResult:
    cands = tuple(Candidate(chunk_id=c, raw_score=s, rank=i) for i, (c, s) in enumerate(scores, 1))
    return VectorSearchResult(
        candidates=cands, requested_k=k, returned_count=len(cands), candidate_exhausted=len(cands) < k, **V.model_dump()
    )


def test_result_invariants_match_the_lexical_contract():
    ok = result(("b", 0.9), ("a", 0.5), ("c", 0.5))
    assert ok.versions == V and ok.candidate_exhausted is True
    with pytest.raises(ValueError, match="non-increasing"):
        result(("a", 0.5), ("b", 0.9))
    with pytest.raises(ValueError, match="chunk_id ascending"):
        result(("b", 0.5), ("a", 0.5))
    with pytest.raises(ValueError, match="unique"):
        result(("a", 0.5), ("a", 0.4))
    with pytest.raises(ValueError, match="candidate_exhausted"):
        VectorSearchResult(candidates=(), requested_k=1, returned_count=0, candidate_exhausted=False, **V.model_dump())


def test_hashing_provider_is_deterministic_unit_norm_and_token_sensitive():
    p, q = HashingEmbeddingProvider(), HashingEmbeddingProvider()
    a = p.embed_query("阿司匹林 用法用量")
    assert len(a) == DIMENSION and math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)
    assert a == q.embed_query("  阿司匹林　用法用量 ")  # same tokens after norm-v1 -> identical
    close = p.embed_query("阿司匹林 禁忌")
    far = p.embed_query("PROT-2024-017 randomisation schedule")
    dot = lambda u, v: sum(x * y for x, y in zip(u, v, strict=True))  # noqa: E731
    assert dot(a, close) > dot(a, far)
    assert p.embed_documents([]) == [] and len(p.embed_documents(["x", "y"])) == 2
    assert p.spec.embedding_version == "emb-hash-test-v1" and p.spec.dimension == DIMENSION
    assert vector_literal([0.5, -1.0]).startswith("[0.5,-1.0")


class FakeRetriever:
    def __init__(self, res, versions=V):
        self._res, self._versions = res, versions

    @property
    def versions(self):
        return self._versions

    def search(self, query, k, *, allow_historical=False):
        return self._res


def test_boundary_bounds_k_query_and_versions_and_revalidates_results():
    good = result(("a", 0.9), k=3)
    assert run_vector_search(FakeRetriever(good), "阿司匹林", 3, expected=V) == good
    for bad_k in (0, 21, True, 1.5):
        with pytest.raises(BusinessError) as exc:
            run_vector_search(FakeRetriever(good), "阿司匹林", bad_k, expected=V)  # type: ignore[arg-type]
        assert exc.value.code is ErrorCode.invalid_request
    with pytest.raises(BusinessError, match="empty after normalization"):
        run_vector_search(FakeRetriever(good), " 　 ", 3, expected=V)
    with pytest.raises(BusinessError) as exc:
        run_vector_search(
            FakeRetriever(good), "阿司匹林", 3, expected=V.model_copy(update={"embedding_version": "other"})
        )
    assert exc.value.code is ErrorCode.version_conflict
    with pytest.raises(InfrastructureError):  # echoes k=5 for a k=3 request
        run_vector_search(FakeRetriever(result(("a", 0.9), k=5)), "阿司匹林", 3, expected=V)
    drifted = good.model_copy(update={"embedding_version": "other"})
    with pytest.raises(InfrastructureError):
        run_vector_search(FakeRetriever(drifted), "阿司匹林", 3, expected=V)
