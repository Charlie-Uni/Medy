"""In-process BM25 index: the OFFLINE REFERENCE BASELINE of ADR-0002.

This is not a production retriever. Baseline 3.7 requires ACL, status and effective-time
filtering inside the database query; an in-process index cannot do that. It may only be used
on a corpus that the caller already fetched through the database with RLS applied, for the
DEC-001 comparison experiment. It must never hold a full production index.

Adapted from the legacy 文枢 project (`app/retrieval/bm25.py`): the scoring formula is kept,
the O(N) term-frequency loop is replaced by an inverted index, department filtering is removed
(authorization happens before the corpus reaches this class), ties are broken by chunk_id
(baseline 3.7), and the output is the `LexicalSearchResult` contract with version metadata.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable

from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.contracts import ChunkRecord, LexicalCandidate, LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.tokenizer import Tokenizer

RETRIEVER_VERSION = "bm25-offline-v1"


class OfflineBM25Index:
    def __init__(self, tokenizer: Tokenizer, k1: float = 1.5, b: float = 0.75) -> None:
        if k1 <= 0 or not 0.0 <= b <= 1.0:
            raise ValueError("k1 must be > 0 and 0 <= b <= 1")
        self.tokenizer = tokenizer
        self.k1 = k1
        self.b = b
        self._postings: dict[str, dict[str, int]] = {}
        self._doc_len: dict[str, int] = {}
        self._avg_len = 0.0
        self._built_with: LexicalVersions | None = None  # snapshot taken by index(); queries must match it

    @property
    def retriever_version(self) -> str:
        return f"{RETRIEVER_VERSION}(k1={self.k1},b={self.b})"

    def _current_versions(self) -> LexicalVersions:
        return LexicalVersions(
            retriever_version=self.retriever_version,
            tokenizer_version=self.tokenizer.tokenizer_version,
            dictionary_version=self.tokenizer.dictionary_version,
            normalization_version=self.tokenizer.normalization_version,
        )

    @property
    def versions(self) -> LexicalVersions:
        """Versions the current index was built with (empty index reports the current configuration)."""
        return self._built_with if self._built_with is not None else self._current_versions()

    @property
    def size(self) -> int:
        return len(self._doc_len)

    def index(self, chunks: Iterable[ChunkRecord]) -> None:
        """Rebuild the index from an already-authorized corpus. Empty chunks are skipped.

        The build is all-or-nothing: everything is assembled in local structures and the live index,
        statistics and version snapshot are replaced together only after every chunk succeeded, so a
        failed (re)build leaves the previous index fully queryable and its versions unchanged."""
        postings: dict[str, dict[str, int]] = {}
        doc_len: dict[str, int] = {}
        seen: set[str] = set()
        versions = self._current_versions()
        for chunk in chunks:
            if chunk.chunk_id in seen:
                raise ValueError(f"duplicate chunk_id {chunk.chunk_id}")
            seen.add(chunk.chunk_id)
            tokens = self.tokenizer.tokenize(chunk.text)
            if not tokens:
                continue
            doc_len[chunk.chunk_id] = len(tokens)
            for term, tf in Counter(tokens).items():
                postings.setdefault(term, {})[chunk.chunk_id] = tf
        self._postings, self._doc_len = postings, doc_len
        self._avg_len = sum(doc_len.values()) / len(doc_len) if doc_len else 0.0
        self._built_with = versions

    def search(self, query: str, k: int) -> LexicalSearchResult:
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("k must be an integer >= 1")
        if self._built_with is not None and self._current_versions() != self._built_with:
            raise InfrastructureError(
                ErrorCode.internal_error,
                retryable=False,
                detail=f"tokenizer configuration drifted from the index: built={self._built_with.model_dump()} now={self._current_versions().model_dump()}; rebuild the index",
            )
        scores: dict[str, float] = {}
        n = len(self._doc_len)
        if n:
            for term, qtf in Counter(self.tokenizer.tokenize(query)).items():
                postings = self._postings.get(term)
                if not postings:
                    continue
                df = len(postings)
                idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
                for chunk_id, tf in postings.items():
                    norm = self.k1 * (1.0 - self.b + self.b * self._doc_len[chunk_id] / self._avg_len)
                    scores[chunk_id] = scores.get(chunk_id, 0.0) + idf * (tf * (self.k1 + 1.0)) / (tf + norm) * qtf
        # Deterministic order: score descending, then chunk_id ascending (baseline 3.7).
        ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
        candidates = tuple(
            LexicalCandidate(chunk_id=chunk_id, raw_score=score, rank=rank)
            for rank, (chunk_id, score) in enumerate(ordered, start=1)
        )
        built = self.versions
        return LexicalSearchResult(
            candidates=candidates,
            requested_k=k,
            returned_count=len(candidates),
            candidate_exhausted=len(candidates) < k,
            retriever_version=built.retriever_version,
            tokenizer_version=built.tokenizer_version,
            dictionary_version=built.dictionary_version,
            normalization_version=built.normalization_version,
        )
