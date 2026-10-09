"""Embedding providers (ADR-0007).

`EmbeddingSpec` is everything that determines a vector's meaning: model, pinned revision, dimension,
normalisation, truncation length and framework. It is stored with the index and compared on every query.
`BgeM3EmbeddingProvider` is the production provider (local inference, optional extra `embed`);
`HashingEmbeddingProvider` is a deterministic, dependency-free stand-in for tests of the database side.
"""

from __future__ import annotations

import hashlib
import math
import os
import random
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from medops.retrieval.lexical.normalization import normalize_text

EMBEDDING_VERSION = "emb-bge-m3-dense-v1"
BGE_M3_MODEL_ID = "BAAI/bge-m3"
BGE_M3_REVISION = "5617a9f61b028005a4858fdac845db406aefb181"
DIMENSION = 1024
MAX_SEQ_LENGTH = 1024
MODEL_CACHE_ENV = "MODEL_CACHE_DIR"  # same key as Settings.model_cache_dir


# the fields that give vectors their meaning: a stored index whose metadata differs in any of them is another index,
# whatever its version label says (`embedding_version` and `framework` are labels, not compared)
EMBEDDING_FIELDS: set[str] = {"model_id", "model_revision", "dimension", "normalization", "max_seq_length"}


class EmbeddingSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    embedding_version: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_revision: str = Field(min_length=1)
    dimension: int = Field(ge=1)
    normalization: str = Field(min_length=1)
    max_seq_length: int = Field(ge=1)
    framework: str = Field(min_length=1)


class EmbeddingProvider(Protocol):
    @property
    def spec(self) -> EmbeddingSpec: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        raise ValueError("zero vector cannot be normalised")
    return [x / norm for x in vector]


def model_cache_dir() -> Path:
    return Path(os.environ.get(MODEL_CACHE_ENV) or Path.home() / ".cache" / "medops-models")


# ------------------------------------------------------------------------------------ test provider

_TOKEN = re.compile(r"[A-Za-z0-9]+|[㐀-䶿一-鿿]")


class HashingEmbeddingProvider:
    """Bag-of-tokens hashing: every token maps to a fixed pseudo-random direction, a text is the normalised sum.
    Deterministic across processes, no model, shared-token texts are close. Test use only."""

    def __init__(self, *, dimension: int = DIMENSION, embedding_version: str = "emb-hash-test-v1") -> None:
        self._spec = EmbeddingSpec(
            embedding_version=embedding_version,
            model_id="hashing-bag-of-tokens",
            model_revision="test",
            dimension=dimension,
            normalization="l2",
            max_seq_length=MAX_SEQ_LENGTH,
            framework="python-stdlib",
        )
        self._cache: dict[str, list[float]] = {}

    @property
    def spec(self) -> EmbeddingSpec:
        return self._spec

    def _direction(self, token: str) -> list[float]:
        cached = self._cache.get(token)
        if cached is None:
            seed = int.from_bytes(hashlib.sha256(token.encode("utf-8")).digest()[:8], "big")
            rng = random.Random(seed)
            cached = _unit([rng.gauss(0.0, 1.0) for _ in range(self._spec.dimension)])
            self._cache[token] = cached
        return cached

    def _embed(self, text: str) -> list[float]:
        tokens = _TOKEN.findall(normalize_text(text).lower()) or ["<empty>"]
        total = [0.0] * self._spec.dimension
        for token in tokens:
            for i, x in enumerate(self._direction(token)):
                total[i] += x
        return _unit(total)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


# ------------------------------------------------------------------------------------ production provider


class BgeM3EmbeddingProvider:
    """`BAAI/bge-m3` dense embeddings, pinned revision, L2-normalised, local inference (CPU by default).
    Requires the optional `embed` extra (sentence-transformers + torch); imported lazily so the API and CI
    never load PyTorch."""

    def __init__(
        self,
        *,
        cache_folder: Path | None = None,
        device: str = "cpu",
        batch_size: int = 16,
        revision: str = BGE_M3_REVISION,
    ) -> None:
        try:
            import sentence_transformers
            import torch
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise RuntimeError(
                "the embedding provider needs the optional 'embed' extra (sentence-transformers)"
            ) from exc
        self._model: Any = sentence_transformers.SentenceTransformer(
            BGE_M3_MODEL_ID,
            revision=revision,
            cache_folder=str(cache_folder or model_cache_dir()),
            device=device,
        )
        self._model.max_seq_length = MAX_SEQ_LENGTH
        self._batch = batch_size
        get_dim = getattr(self._model, "get_embedding_dimension", None) or self._model.get_sentence_embedding_dimension
        dimension = int(get_dim())
        if dimension != DIMENSION:
            raise RuntimeError(f"model dimension {dimension} != {DIMENSION}")
        self._spec = EmbeddingSpec(
            embedding_version=EMBEDDING_VERSION,
            model_id=BGE_M3_MODEL_ID,
            model_revision=revision,
            dimension=DIMENSION,
            normalization="l2",
            max_seq_length=MAX_SEQ_LENGTH,
            framework=f"sentence-transformers {sentence_transformers.__version__}; torch {torch.__version__}; device {device}",
        )

    @property
    def spec(self) -> EmbeddingSpec:
        return self._spec

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            [normalize_text(t) for t in texts],
            batch_size=self._batch,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [[float(x) for x in row] for row in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
