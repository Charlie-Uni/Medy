"""Shared retrieval assembly for API requests and evaluation runners.

The caller owns the identity-bound transaction and policy selection. Both channels receive the same effective
date. An experimental lexical factory must accept that date explicitly; it must never capture a stale run date.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from typing import Any, Protocol

from medops.domain.identity import UserContext
from medops.harness.retrieval_port import ProductionRetrieval
from medops.retrieval.cache import CandidateCache
from medops.retrieval.contracts import LexicalRetriever
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.production import (
    production_hybrid_config,
    production_lexical_retriever,
    production_lexical_versions,
    production_vector_retriever,
)
from medops.retrieval.rerank import Reranker
from medops.retrieval.rewrite import Glossary
from medops.retrieval.vector.embedding import EmbeddingProvider


class DatedLexicalFactory(Protocol):
    def __call__(self, conn: Any, *, as_of: date | None) -> LexicalRetriever: ...


def build_retrieval(
    *,
    conn_for_user: Callable[[UserContext], AbstractContextManager[Any]],
    provider: EmbeddingProvider,
    reranker: Reranker,
    as_of: date | None,
    config: HybridConfig | None = None,
    lexical_factory: DatedLexicalFactory | None = None,
    glossary: Glossary | None = None,
    multi_query: bool = False,
    doc_focus: bool = False,
    source_constraint: bool = False,
    translator: Callable[[str], str | None] | None = None,
    cache: CandidateCache | None = None,
    cache_versions: tuple[str, str] | None = None,
) -> ProductionRetrieval:
    lexical = lexical_factory if lexical_factory is not None else production_lexical_retriever
    return ProductionRetrieval(
        conn_for_user=conn_for_user,
        lexical_factory=lambda conn: lexical(conn, as_of=as_of),
        vector_factory=lambda conn: production_vector_retriever(conn, provider, as_of=as_of),
        reranker=reranker,
        config=config or production_hybrid_config(),
        lexical_versions=None if lexical_factory is not None else production_lexical_versions(),
        glossary=glossary,
        multi_query=multi_query,
        doc_focus=doc_focus,
        source_constraint=source_constraint,
        translator=translator,
        cache=cache,
        cache_versions=cache_versions,
    )
