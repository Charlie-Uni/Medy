"""Composite retrieval_version (baseline 3.6, M1-15): fixed formula, every member matters, closed input."""

import math

import pytest
from pydantic import ValidationError

from medops.core.canonical import canonical_json, sha256_hex
from medops.retrieval.contracts import LexicalVersions
from medops.retrieval.versioning import RETRIEVAL_VERSION_FIELDS, RetrievalVersionInputs, compute_retrieval_version

FIXTURE = {
    "retriever_version": "pg-simple-fts@1",
    "tokenizer_version": "jieba-v1",
    "dictionary_version": "dict-none",
    "normalization_version": "norm-v1",
    "embedding_version": "embed-undecided",
    "rrf_params": {"k": 60},
    "rerank_params": {},
    "candidate_limits": {"lexical_k": 20, "vector_k": 20, "rerank_input": 20, "rerank_output": 8},
}
# Computed once from the baseline 3.6 formula (CPython 3.11.16, macOS arm64, 2026-09-17); any drift
# here would silently invalidate cache keys, operation keys and replay records.
FIXTURE_VERSION = "b649d904a40ecb58bd649b08b7aa2d08f8423e8bea9b86a96ab2e41aa38c48e1"


def test_members_are_exactly_the_eight_named_in_baseline_3_6():
    assert RETRIEVAL_VERSION_FIELDS == (
        "retriever_version",
        "tokenizer_version",
        "dictionary_version",
        "normalization_version",
        "embedding_version",
        "rrf_params",
        "rerank_params",
        "candidate_limits",
    )
    # Later optional policy members join the hash only when set, so historical eight-member composites remain exact.
    assert tuple(RetrievalVersionInputs.model_fields) == (
        *RETRIEVAL_VERSION_FIELDS,
        "vector_retriever_version",
        "rewrite_params",
    )


def test_known_answer_and_formula():
    inputs = RetrievalVersionInputs(**FIXTURE)
    version = compute_retrieval_version(inputs)
    assert version == FIXTURE_VERSION
    assert version == sha256_hex(canonical_json(FIXTURE))  # independent re-derivation of the formula
    assert len(version) == 64 and int(version, 16) >= 0


@pytest.mark.parametrize(
    "field,new_value",
    [
        ("retriever_version", "pg-search-bm25@1"),
        ("tokenizer_version", "jieba-v2"),
        ("dictionary_version", "dict-meddra-v1"),
        ("normalization_version", "norm-v2"),
        ("embedding_version", "bge-m3@1024"),
        ("vector_retriever_version", "pgvector-generic-plan-v2"),
        ("rrf_params", {"k": 61}),
        ("rrf_params", {"k": 60, "weights": {"lexical": 1, "vector": 1}}),
        ("rerank_params", {"model": "reranker-x", "version": "1"}),
        ("candidate_limits", {**FIXTURE["candidate_limits"], "rerank_output": 5}),
        ("candidate_limits", {**FIXTURE["candidate_limits"], "over_fetch": 3}),
    ],
)
def test_every_member_and_every_nested_parameter_changes_the_version(field, new_value):
    changed = RetrievalVersionInputs(**{**FIXTURE, field: new_value})
    assert compute_retrieval_version(changed) != FIXTURE_VERSION


def test_version_is_independent_of_key_order_and_construction_path():
    reordered = {k: FIXTURE[k] for k in reversed(list(FIXTURE))}
    reordered["candidate_limits"] = dict(reversed(list(FIXTURE["candidate_limits"].items())))
    assert compute_retrieval_version(RetrievalVersionInputs(**reordered)) == FIXTURE_VERSION
    lexical = LexicalVersions(
        retriever_version="pg-simple-fts@1",
        tokenizer_version="jieba-v1",
        dictionary_version="dict-none",
        normalization_version="norm-v1",
    )
    via_lexical = RetrievalVersionInputs.from_lexical(
        lexical,
        embedding_version="embed-undecided",
        rrf_params={"k": 60},
        rerank_params={},
        candidate_limits=FIXTURE["candidate_limits"],
    )
    assert compute_retrieval_version(via_lexical) == FIXTURE_VERSION
    assert via_lexical.lexical == lexical


def test_component_versions_alone_do_not_identify_the_configuration():
    """Same LexicalVersions, different RRF k: the diagnostics agree but the composite must differ,
    which is why baseline 3.6 forbids using the components as cache or replay keys."""
    a = RetrievalVersionInputs(**FIXTURE)
    b = RetrievalVersionInputs(**{**FIXTURE, "rrf_params": {"k": 30}})
    assert a.lexical == b.lexical
    assert compute_retrieval_version(a) != compute_retrieval_version(b)


@pytest.mark.parametrize(
    "bad",
    [
        {**FIXTURE, "extra_member": "x"},  # unknown member would be silently missing from the hash
        {k: v for k, v in FIXTURE.items() if k != "embedding_version"},  # missing member
        {**FIXTURE, "tokenizer_version": ""},
        {**FIXTURE, "vector_retriever_version": ""},
        {**FIXTURE, "rrf_params": {}},  # no k
        {**FIXTURE, "rrf_params": {"k": 0}},
        {**FIXTURE, "rrf_params": {"k": -60}},
        {**FIXTURE, "rrf_params": {"k": True}},  # bool is not a number here
        {**FIXTURE, "rrf_params": {"k": "60"}},
        {**FIXTURE, "rrf_params": {"k": math.nan}},  # canonical JSON forbids NaN
        {**FIXTURE, "rerank_params": {"threshold": math.inf}},
        {**FIXTURE, "candidate_limits": {}},
        {**FIXTURE, "candidate_limits": {"lexical_k": 0}},
        {**FIXTURE, "candidate_limits": {"lexical_k": 2.5}},
    ],
)
def test_rejects_inputs_that_would_hash_ambiguously_or_describe_no_valid_retrieval(bad):
    with pytest.raises(ValidationError):
        RetrievalVersionInputs(**bad)


def test_inputs_are_frozen():
    inputs = RetrievalVersionInputs(**FIXTURE)
    with pytest.raises(ValidationError):
        inputs.embedding_version = "other"  # type: ignore[misc]
