"""Production retrieval configuration (M1-14 / M1-15; DEC-001 final judgement, ADR-0002; DEC-002, ADR-0007).

Everything that shapes production retrieval results is pinned here and nowhere else:

- lexical: candidate A2 = PostgreSQL `simple` full-text search over application-side jieba tokens
  (`tok-jieba-v2`) with the vendored English stopword list whose SHA-256 is fixed below; the index lives in the
  migration-created table `chunk_lexical_tsv` under the index name `production-lexical`;
- vector: bge-m3 dense embeddings (`emb-bge-m3-dense-v1`) in `chunk_embeddings` (migration 0006);
- fusion: rank-only RRF with k=60 over top-20/top-20, fused limit 20;
- reranker: bge-reranker-v2-m3 on the re-checked candidates, output 8.

`PRODUCTION_RETRIEVAL_VERSION` is the SHA-256 composite of baseline 3.6 over exactly these members. It is the
only retrieval identifier allowed in cache keys, operation keys and replay records; changing any member here
changes it, and the unit test pins the current value so that an accidental change is caught in review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import date
from importlib import resources
from pathlib import Path
from typing import Any

import psycopg

from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.contracts import LexicalVersions
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.lexical import index_consumer, pg_simple_fts
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV2
from medops.retrieval.rerank import MAX_INPUT, MAX_LENGTH, RERANK_MODEL_ID, RERANK_REVISION, RerankerSpec
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.embedding import EMBEDDING_VERSION, EmbeddingProvider
from medops.retrieval.versioning import RetrievalVersionInputs, compute_retrieval_version

PRODUCTION_LEXICAL_CANDIDATE = "A2"
PRODUCTION_LEXICAL_TABLE = "chunk_lexical_tsv"
PRODUCTION_LEXICAL_INDEX_NAME = "production-lexical"
STOPWORDS_RESOURCE = "english.stop"
STOPWORDS_SHA256 = "b3f772a000465cb76e23adb03b47073c591c156fad8f7af09c8b8e80d6bd8eac"
RERANK_OUTPUT = 8

PRODUCTION_RERANKER_SPEC = RerankerSpec(
    reranker_version="rerank-bge-v2-m3-v1",
    model_id=RERANK_MODEL_ID,
    model_revision=RERANK_REVISION,
    max_length=MAX_LENGTH,
    max_input=MAX_INPUT,
    output=RERANK_OUTPUT,
)


def stopwords_path() -> Path:
    path = Path(str(resources.files("medops.retrieval.lexical").joinpath("resources", STOPWORDS_RESOURCE)))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != STOPWORDS_SHA256:
        raise InfrastructureError(
            ErrorCode.internal_error, detail="vendored stopword list differs from the pinned SHA-256", retryable=False
        )
    return path


_TOKENIZER: dict[str, JiebaTokenizerV2] = {}


def production_tokenizer() -> JiebaTokenizerV2:
    """One instance per process (jieba dictionary load belongs to start-up, not to a query)."""
    if "t" not in _TOKENIZER:
        _TOKENIZER["t"] = JiebaTokenizerV2(stopwords=stopwords_path())
    return _TOKENIZER["t"]


def production_lexical_versions() -> LexicalVersions:
    return pg_simple_fts.configured_versions(production_tokenizer())


def production_hybrid_config() -> HybridConfig:
    return HybridConfig(k_lexical=20, k_vector=20, rrf_k=60.0, limit=20)


def production_retrieval_inputs(
    config: HybridConfig | None = None, *, rerank_output: int = RERANK_OUTPUT
) -> RetrievalVersionInputs:
    """Defaults are the pinned production values; a released retrieval policy (M4-03) passes its effective config so the
    composite version changes with it (baseline 3.6)."""
    config = config or production_hybrid_config()
    return RetrievalVersionInputs.from_lexical(
        production_lexical_versions(),
        embedding_version=EMBEDDING_VERSION,
        rrf_params=config.rrf_params(),
        rerank_params=PRODUCTION_RERANKER_SPEC.rerank_params(),
        candidate_limits={**config.candidate_limits(), "rerank_output": rerank_output},
    )


def production_retrieval_version() -> str:
    return compute_retrieval_version(production_retrieval_inputs())


PRODUCTION_RETRIEVAL_VERSION = "90b57e4e86b4bb462fc4de58f7f7749666fb6f50a588c129bd5f9aa50585ab18"  # pinned; see tests


def production_lexical_retriever(
    conn: psycopg.Connection[Any], *, as_of: date | None = None
) -> pg_simple_fts.PgSimpleFtsRetriever:
    return pg_simple_fts.PgSimpleFtsRetriever(
        conn,
        production_tokenizer(),
        as_of=as_of,
        index_name=PRODUCTION_LEXICAL_INDEX_NAME,
        table=PRODUCTION_LEXICAL_TABLE,
    )


def production_vector_retriever(
    conn: psycopg.Connection[Any], provider: EmbeddingProvider, *, as_of: date | None = None
) -> pg_vector.PgVectorRetriever:
    if provider.spec.embedding_version != EMBEDDING_VERSION:
        raise InfrastructureError(
            ErrorCode.internal_error,
            detail="production vector retriever requires the pinned embedding version",
            retryable=False,
        )
    return pg_vector.PgVectorRetriever(conn, provider, as_of=as_of)


def build_production_lexical_index(
    conn: psycopg.Connection[Any], *, built_by: str, batch: int = 500
) -> pg_simple_fts.IndexBuildReport:
    """(Re)build the production lexical index in the migration-created table (admin connection)."""
    return pg_simple_fts.build_index(
        conn,
        production_tokenizer(),
        built_by=built_by,
        batch=batch,
        index_name=PRODUCTION_LEXICAL_INDEX_NAME,
        table=PRODUCTION_LEXICAL_TABLE,
    )


def production_index_target() -> index_consumer.IndexTarget:
    """Outbox consumer target that keeps the production lexical index in step with document status."""
    return index_consumer.tsvector_target(PRODUCTION_LEXICAL_TABLE, production_tokenizer())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Production retrieval configuration tools")
    parser.add_argument("action", choices=("show", "build-lexical"))
    parser.add_argument("--admin-url", help="admin DSN (default: DATABASE_ADMIN_URL from settings)")
    parser.add_argument("--built-by", default="production-build")
    args = parser.parse_args(argv)
    if args.action == "show":
        print(
            json.dumps(
                {
                    "retrieval_version": production_retrieval_version(),
                    "inputs": production_retrieval_inputs().model_dump(mode="json"),
                    "lexical_table": PRODUCTION_LEXICAL_TABLE,
                    "lexical_index_name": PRODUCTION_LEXICAL_INDEX_NAME,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    from medops.core.config import Settings

    dsn = args.admin_url
    if not dsn:
        settings = Settings()  # type: ignore[call-arg]
        dsn = (settings.database_admin_url or settings.database_url).get_secret_value()
    with psycopg.connect(dsn) as conn:
        report = build_production_lexical_index(conn, built_by=args.built_by)
        conn.commit()
    print(json.dumps(report.as_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
