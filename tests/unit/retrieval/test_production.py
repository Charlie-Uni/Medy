"""M1-15: the production retrieval configuration is pinned and its composite retrieval_version is stable;
any member change changes the composite (and this test) on purpose."""

from __future__ import annotations

import hashlib

import pytest

from medops.core.errors import InfrastructureError
from medops.retrieval import production
from medops.retrieval.versioning import compute_retrieval_version

pytest.importorskip("jieba")


def test_pinned_members_and_composite_version():
    inputs = production.production_retrieval_inputs()
    assert inputs.retriever_version == "pg-simple-fts-v1"
    assert inputs.tokenizer_version == "tok-jieba-v2"
    assert inputs.dictionary_version.endswith("+stop:" + production.STOPWORDS_SHA256[:16])
    assert inputs.normalization_version == "norm-v1"
    assert inputs.embedding_version == "emb-bge-m3-dense-v1"
    assert inputs.rrf_params == {"k": 60.0, "method": "rrf-rank-only"}
    assert inputs.rerank_params["model_id"] == "BAAI/bge-reranker-v2-m3" and inputs.rerank_params["output"] == 8
    assert inputs.candidate_limits == {"lexical_k": 20, "vector_k": 20, "fused_limit": 20, "rerank_output": 8}
    assert (
        compute_retrieval_version(inputs)
        == production.PRODUCTION_RETRIEVAL_VERSION
        == production.production_retrieval_version()
    )
    assert len(production.PRODUCTION_RETRIEVAL_VERSION) == 64


def test_any_member_change_changes_the_composite():
    base = production.production_retrieval_inputs()
    for change in (
        {"tokenizer_version": "tok-jieba-v3"},
        {"embedding_version": "emb-other"},
        {"rrf_params": {"k": 61.0, "method": "rrf-rank-only"}},
        {"rerank_params": {**base.rerank_params, "output": 5}},
        {"candidate_limits": {**base.candidate_limits, "lexical_k": 10}},
    ):
        assert compute_retrieval_version(base.model_copy(update=change)) != production.PRODUCTION_RETRIEVAL_VERSION, (
            change
        )


def test_stopword_file_is_verified_against_the_pin(monkeypatch, tmp_path):
    path = production.stopwords_path()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == production.STOPWORDS_SHA256
    monkeypatch.setattr(production, "STOPWORDS_SHA256", "0" * 64)
    with pytest.raises(InfrastructureError):
        production.stopwords_path()


def test_vector_retriever_requires_the_pinned_embedding_version():
    from medops.retrieval.vector.embedding import HashingEmbeddingProvider

    with pytest.raises(InfrastructureError):
        production.production_vector_retriever(None, HashingEmbeddingProvider())  # type: ignore[arg-type]


def test_a_released_glossary_joins_the_composite_and_none_leaves_it_unchanged():
    base = production.production_retrieval_inputs()
    none = production.production_retrieval_inputs(glossary_version="glossary-none")
    assert compute_retrieval_version(none) == production.PRODUCTION_RETRIEVAL_VERSION
    assert none.rewrite_params == {}
    with_glossary = production.production_retrieval_inputs(glossary_version="glossary-20260926-0123456789ab")
    assert with_glossary.rewrite_params == {"glossary": "glossary-20260926-0123456789ab"}
    assert compute_retrieval_version(with_glossary) != production.PRODUCTION_RETRIEVAL_VERSION
    assert compute_retrieval_version(base) == production.PRODUCTION_RETRIEVAL_VERSION


def test_multi_query_joins_the_composite_only_when_on():
    off = production.production_retrieval_inputs(multi_query=False)
    assert compute_retrieval_version(off) == production.PRODUCTION_RETRIEVAL_VERSION
    on = production.production_retrieval_inputs(multi_query=True)
    assert on.rewrite_params == {"multi_query": True}
    assert compute_retrieval_version(on) != production.PRODUCTION_RETRIEVAL_VERSION
