"""Reusable adapter contract for any `LexicalRetriever` (M1-03).

Apply it to every implementation (offline BM25 today, the DEC-001 production candidates later) with
an already-authorized corpus. The synthetic corpus has KNOWN match counts per term, so the harness
checks how many candidates an adapter must return, not just that its exhaustion flag is
self-consistent: zero matches, fewer than K, exactly K, more than K, and tie ordering.
Production exact-count and RLS checks remain later milestones.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from medops.core.errors import BusinessError, ErrorCode
from medops.retrieval.contracts import ChunkRecord, LexicalRetriever, LexicalSearchResult
from medops.retrieval.lexical.boundary import MAX_K, run_lexical_search

# Term -> number of chunks containing it. ASCII terms tokenize identically under every tokenizer.
FIXTURE_TERMS: dict[str, int] = {"alpha": 1, "beta": 3, "gamma": 7, "delta": 25}


def build_fixture_corpus() -> list[ChunkRecord]:
    """Chunk i contains term T iff i < FIXTURE_TERMS[T]; every chunk also has a unique filler token."""
    n = max(FIXTURE_TERMS.values())
    corpus = []
    for i in range(n):
        terms = [t for t, count in FIXTURE_TERMS.items() if i < count]
        corpus.append(ChunkRecord(chunk_id=f"c{i:03d}", text=" ".join(terms + [f"filler{i:03d}"])))
    return corpus


def _search(retriever: LexicalRetriever, query: str, k: int) -> LexicalSearchResult:
    return run_lexical_search(retriever, query, k, expected=retriever.versions)


def assert_lexical_adapter_contract(build: Callable[[Sequence[ChunkRecord]], LexicalRetriever]) -> None:
    """`build(corpus)` returns an adapter indexed over `corpus`."""
    corpus = build_fixture_corpus()
    retriever = build(corpus)
    versions = retriever.versions
    corpus_ids = {c.chunk_id for c in corpus}

    # counts: zero, fewer than K, exactly K, more than K (K chosen per term)
    zero = _search(retriever, "omega", 5)
    assert zero.returned_count == 0 and zero.candidate_exhausted is True
    for term, matches in FIXTURE_TERMS.items():
        expected_ids = {f"c{i:03d}" for i in range(matches)}
        for k in sorted({1, min(matches, MAX_K), min(matches + 1, MAX_K), MAX_K}):
            result = _search(retriever, term, k)
            assert result == _search(retriever, term, k), "results must be deterministic"
            assert result.versions == versions and result.requested_k == k
            assert {c.chunk_id for c in result.candidates} <= expected_ids, f"{term}: non-matching chunk returned"
            expected_count = min(matches, k)
            assert result.returned_count == expected_count, (
                f"{term}: k={k} returned {result.returned_count}, expected {expected_count}"
            )
            assert result.candidate_exhausted == (matches < k), f"{term}: exhaustion flag wrong for k={k}"
            assert {c.chunk_id for c in result.candidates} <= corpus_ids
    # tie ordering: every 'beta' chunk has identical text length and term frequency, so scores tie
    beta = _search(retriever, "beta", MAX_K)
    scores = [c.raw_score for c in beta.candidates]
    assert scores == sorted(scores, reverse=True)
    for earlier, later in zip(beta.candidates, beta.candidates[1:], strict=False):
        if earlier.raw_score == later.raw_score:
            assert earlier.chunk_id < later.chunk_id, "equal scores must be ordered by chunk_id ascending"
    # version gate: the boundary refuses a run configuration that differs from the index build
    mismatch = versions.model_copy(update={"dictionary_version": versions.dictionary_version + "+other"})
    try:
        run_lexical_search(retriever, "alpha", 5, expected=mismatch)
    except BusinessError as exc:
        assert exc.code is ErrorCode.version_conflict
    else:
        raise AssertionError("boundary must reject mismatched versions")
