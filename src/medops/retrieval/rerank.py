"""Reranker stage (ADR-0007 §4; baseline 5.2 "Reranker 输入最多 20 个候选，输出最多 5-8 个").

The reranker orders ALREADY RE-CHECKED evidence: it receives `Evidence` (whose text is the stored chunk
content), never raw index hits, so nothing it returns can bypass the fact plane. It is deterministic for a
fixed model revision; its spec (`rerank_params`) enters `retrieval_version`. `BgeRerankerV2M3` is the
production cross-encoder (local inference, optional extra `embed`); `OverlapReranker` is a dependency-free
stand-in for tests.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from medops.domain.evidence import Evidence
from medops.retrieval.lexical.normalization import normalize_text

RERANK_MODEL_ID = "BAAI/bge-reranker-v2-m3"
RERANK_REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
MAX_INPUT = 20
DEFAULT_OUTPUT = 8
MAX_LENGTH = 512


class RerankerSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reranker_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    max_length: int = Field(ge=1)
    max_input: int = Field(ge=1, le=MAX_INPUT)
    output: int = Field(ge=1, le=MAX_INPUT)

    def rerank_params(self) -> dict[str, Any]:
        return self.model_dump()


class Reranker(Protocol):
    @property
    def spec(self) -> RerankerSpec: ...

    def score(self, query: str, texts: Sequence[str]) -> list[float]: ...


class RankedEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    evidence: Evidence
    score: float
    rank: int = Field(ge=1)


def rerank_evidence(reranker: Reranker, query: str, evidence: Sequence[Evidence]) -> tuple[RankedEvidence, ...]:
    """Score at most `spec.max_input` evidence items and keep the best `spec.output`; ties break by chunk_id."""
    spec = reranker.spec
    if len(evidence) > spec.max_input:
        raise ValueError(f"reranker input exceeds {spec.max_input} candidates")
    if not evidence:
        return ()
    text = normalize_text(query)
    scores = reranker.score(text, [e.text for e in evidence])
    if len(scores) != len(evidence):
        raise ValueError("reranker returned a score count that differs from the input")
    ordered = sorted(zip(evidence, scores, strict=True), key=lambda pair: (-pair[1], pair[0].citation.chunk_id))
    return tuple(
        RankedEvidence(evidence=e, score=float(s), rank=i) for i, (e, s) in enumerate(ordered[: spec.output], start=1)
    )


# ------------------------------------------------------------------------------------ test reranker

_TOKEN = re.compile(r"[A-Za-z0-9]+|[㐀-䶿一-鿿]")


class OverlapReranker:
    """Token-overlap ratio; deterministic and dependency-free (tests only)."""

    def __init__(self, *, output: int = DEFAULT_OUTPUT) -> None:
        self._spec = RerankerSpec(
            reranker_version="rerank-overlap-test-v1",
            model_id="token-overlap",
            model_revision="test",
            max_length=MAX_LENGTH,
            max_input=MAX_INPUT,
            output=output,
        )

    @property
    def spec(self) -> RerankerSpec:
        return self._spec

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        q = set(_TOKEN.findall(query.lower()))
        out = []
        for t in texts:
            tokens = set(_TOKEN.findall(normalize_text(t).lower()))
            out.append(len(q & tokens) / len(q) if q else 0.0)
        return out


# ------------------------------------------------------------------------------------ production reranker


class BgeRerankerV2M3:
    def __init__(
        self,
        *,
        cache_folder: Path | None = None,
        device: str = "cpu",
        batch_size: int = 8,
        output: int = DEFAULT_OUTPUT,
        revision: str = RERANK_REVISION,
    ) -> None:
        try:
            import sentence_transformers
        except ImportError as exc:  # pragma: no cover - only without the extra
            raise RuntimeError("the reranker needs the optional 'embed' extra (sentence-transformers)") from exc
        from medops.retrieval.vector.embedding import model_cache_dir

        self._model: Any = sentence_transformers.CrossEncoder(
            RERANK_MODEL_ID,
            revision=revision,
            cache_folder=str(cache_folder or model_cache_dir()),
            device=device,
            max_length=MAX_LENGTH,
        )
        self._batch = batch_size
        self._spec = RerankerSpec(
            reranker_version="rerank-bge-v2-m3-v1",
            model_id=RERANK_MODEL_ID,
            model_revision=revision,
            max_length=MAX_LENGTH,
            max_input=MAX_INPUT,
            output=output,
        )
        self.framework = f"sentence-transformers {sentence_transformers.__version__}; device {device}"

    @property
    def spec(self) -> RerankerSpec:
        return self._spec

    def score(self, query: str, texts: Sequence[str]) -> list[float]:
        if not texts:
            return []
        pairs = [(query, normalize_text(t)) for t in texts]
        scores = self._model.predict(pairs, batch_size=self._batch, show_progress_bar=False)
        return [float(s) for s in scores]


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
