"""pgvector adapter (M1-16; ADR-0007; baseline 3.7).

Fixed recipe (any change is a new `RETRIEVER_VERSION`):
- candidates: every chunk that has a vector of the configured `embedding_version` AND is visible through the
  RLS chain `chunk_embeddings -> chunks -> documents -> document_acl` of the ordinary role AND belongs to an
  `active` document whose effective window contains `as_of` (an `archived` one too when the caller explicitly
  asked for historical evidence, INV-DATA-03);
- ranking: cosine distance ascending via the HNSW index with pgvector's iterative scan (`relaxed_order`) so
  filtering cannot silently starve the page; ties broken by `chunk_id` ascending after an exact re-sort of the
  returned page;
- exact count: the eligible set does not depend on the query text for vectors, so its exact size is counted in
  the same transaction under the same filters; the page must be exactly `min(eligible, k)` long, otherwise the
  adapter fails closed (hard gate 4: no silent shortfall);
- versions: the index metadata (`embedding_index_meta`) is the truth about what was built; a provider whose
  spec differs in any field is refused (baseline 3.6 rule applied to embeddings).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

import psycopg

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text
from medops.retrieval.lexical.pg_lexical_common import check_k, require_identity
from medops.retrieval.vector.contracts import Candidate, VectorSearchResult, VectorVersions
from medops.retrieval.vector.embedding import EmbeddingProvider, EmbeddingSpec

RETRIEVER_VERSION = "pgvector-hnsw-cosine-v1"
TABLE = "chunk_embeddings"
META_TABLE = "embedding_index_meta"
INDEX_NAME = "chunk_embeddings_hnsw_cosine"
MIN_EF_SEARCH = 40
MAX_EF_SEARCH = 1000

ELIGIBLE_COUNT_SQL = f"""
select count(*)
from {TABLE} e
join chunks c on c.chunk_id = e.chunk_id
join documents d on d.doc_id = c.doc_id
where e.embedding_version = %(v)s
  and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
  and d.effective_from <= %(as_of)s
  and (d.effective_to is null or d.effective_to > %(as_of)s)
  and (%(doc_ids)s::uuid[] is null or c.doc_id = any(%(doc_ids)s::uuid[]))
"""

SEARCH_SQL = f"""
select e.chunk_id, e.embedding <=> %(q)s::vector as distance
from {TABLE} e
join chunks c on c.chunk_id = e.chunk_id
join documents d on d.doc_id = c.doc_id
where e.embedding_version = %(v)s
  and (d.status = 'active' or (%(allow_historical)s and d.status = 'archived'))
  and d.effective_from <= %(as_of)s
  and (d.effective_to is null or d.effective_to > %(as_of)s)
  and (%(doc_ids)s::uuid[] is null or c.doc_id = any(%(doc_ids)s::uuid[]))
order by e.embedding <=> %(q)s::vector
limit %(k)s
"""


def vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in values) + "]"


@dataclass(frozen=True)
class VectorBuildReport:
    embedding_version: str
    embedded_now: int
    chunk_count: int
    spec: EmbeddingSpec

    def as_dict(self) -> dict[str, Any]:
        return {
            "embedding_version": self.embedding_version,
            "embedded_now": self.embedded_now,
            "chunk_count": self.chunk_count,
            "spec": self.spec.model_dump(),
        }


def read_meta(conn: psycopg.Connection[Any], embedding_version: str) -> EmbeddingSpec:
    row = conn.execute(
        f"select model_id, model_revision, dimension, normalization, max_seq_length, framework "
        f"from {META_TABLE} where embedding_version = %s",
        (embedding_version,),
    ).fetchone()
    if row is None:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable,
            detail=f"embedding index '{embedding_version}' has not been built (no {META_TABLE} row)",
            retryable=False,
        )
    return EmbeddingSpec(
        embedding_version=embedding_version,
        model_id=row[0],
        model_revision=row[1],
        dimension=int(row[2]),
        normalization=row[3],
        max_seq_length=int(row[4]),
        framework=row[5],
    )


def build_index(
    conn: psycopg.Connection[Any],
    provider: EmbeddingProvider,
    *,
    built_by: str,
    batch: int = 64,
    doc_ids: Sequence[str | UUID] | None = None,
) -> VectorBuildReport:
    """Embed every chunk that has no vector of the provider's version yet (admin connection). Re-running only
    fills gaps; a different spec under the same version is refused because the meaning of the vectors would
    silently change. `doc_ids` bounds incremental outbox work to the affected documents; None builds all."""
    if batch <= 0:
        raise ValueError("embedding batch must be positive")
    spec = provider.spec
    existing = conn.execute(
        f"select model_id, model_revision, dimension, normalization, max_seq_length from {META_TABLE} "
        f"where embedding_version = %s",
        (spec.embedding_version,),
    ).fetchone()
    if existing is not None and tuple(existing) != (
        spec.model_id,
        spec.model_revision,
        spec.dimension,
        spec.normalization,
        spec.max_seq_length,
    ):
        raise BusinessError(
            ErrorCode.version_conflict,
            "embedding_version already built with a different model configuration; use a new embedding_version",
        )
    if existing is None:
        conn.execute(
            f"""insert into {META_TABLE} (embedding_version, model_id, model_revision, dimension, normalization,
                                          max_seq_length, framework, chunk_count, built_by)
                values (%s, %s, %s, %s, %s, %s, %s, 0, %s)""",
            (
                spec.embedding_version,
                spec.model_id,
                spec.model_revision,
                spec.dimension,
                spec.normalization,
                spec.max_seq_length,
                spec.framework,
                built_by,
            ),
        )
    rows = conn.execute(
        f"""select c.chunk_id, c.content from chunks c
            where not exists (select 1 from {TABLE} e where e.chunk_id = c.chunk_id and e.embedding_version = %s)
              and (%s::uuid[] is null or c.doc_id = any(%s::uuid[]))
            order by c.chunk_id""",
        (
            spec.embedding_version,
            list(doc_ids) if doc_ids is not None else None,
            list(doc_ids) if doc_ids is not None else None,
        ),
    ).fetchall()
    embedded = 0
    with conn.cursor() as cur:
        for start in range(0, len(rows), batch):
            part = rows[start : start + batch]
            vectors = provider.embed_documents([content for _, content in part])
            for (chunk_id, _), vector in zip(part, vectors, strict=True):
                if len(vector) != spec.dimension:
                    raise InfrastructureError(
                        ErrorCode.internal_error,
                        detail="provider returned a vector of the wrong dimension",
                        retryable=False,
                    )
                cur.execute(
                    f"insert into {TABLE} (chunk_id, embedding_version, embedding) values (%s, %s, %s::vector) "
                    f"on conflict (chunk_id, embedding_version) do nothing",
                    (chunk_id, spec.embedding_version, vector_literal(vector)),
                )
                embedded += cur.rowcount
    total = conn.execute(
        f"select count(*) from {TABLE} where embedding_version = %s", (spec.embedding_version,)
    ).fetchone()
    count = int(total[0]) if total else 0
    conn.execute(
        f"update {META_TABLE} set chunk_count = %s, built_by = %s, built_at = now(), framework = %s where embedding_version = %s",
        (count, built_by, spec.framework, spec.embedding_version),
    )
    return VectorBuildReport(spec.embedding_version, embedded, count, spec)


class PgVectorRetriever:
    """`VectorRetriever` over an ORDINARY-ROLE connection inside the identity-bound request transaction."""

    def __init__(
        self,
        conn: psycopg.Connection[Any],
        provider: EmbeddingProvider,
        *,
        as_of: date | None = None,
        ef_search: int | None = None,
    ) -> None:
        self._conn = conn
        self._provider = provider
        self._as_of = as_of
        self._ef_search = ef_search

    @property
    def configured(self) -> VectorVersions:
        return VectorVersions(
            retriever_version=RETRIEVER_VERSION,
            embedding_version=self._provider.spec.embedding_version,
            normalization_version=NORMALIZATION_VERSION,
        )

    @property
    def versions(self) -> VectorVersions:
        """What the index in the database was BUILT with; the whole spec must match the provider's."""
        built = read_meta(self._conn, self._provider.spec.embedding_version)
        mine = self._provider.spec
        if (built.model_id, built.model_revision, built.dimension, built.normalization, built.max_seq_length) != (
            mine.model_id,
            mine.model_revision,
            mine.dimension,
            mine.normalization,
            mine.max_seq_length,
        ):
            raise BusinessError(
                ErrorCode.version_conflict,
                "embedding index and query provider differ in model configuration; rebuild or use the matching provider",
                detail=f"index={built.model_dump()} query={mine.model_dump()}",
            )
        return VectorVersions(
            retriever_version=RETRIEVER_VERSION,
            embedding_version=built.embedding_version,
            normalization_version=NORMALIZATION_VERSION,
        )

    def _ef(self, k: int) -> int:
        if self._ef_search is not None:
            return max(k, self._ef_search)
        return min(MAX_EF_SEARCH, max(MIN_EF_SEARCH, 4 * k))

    def eligible_count(self, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None) -> int:
        params = {
            "v": self._provider.spec.embedding_version,
            "as_of": self._as_of or date.today(),
            "allow_historical": bool(allow_historical),
            "doc_ids": list(doc_ids) if doc_ids else None,
        }
        row = self._conn.execute(ELIGIBLE_COUNT_SQL, params).fetchone()
        return int(row[0]) if row else 0

    def search(
        self, query: str, k: int, *, allow_historical: bool = False, doc_ids: Sequence[str] | None = None
    ) -> VectorSearchResult:
        check_k(k)
        require_identity(self._conn)
        built = self.versions
        text = normalize_text(query)
        if not text:
            raise BusinessError(ErrorCode.invalid_request, "query is empty after normalization")
        eligible = self.eligible_count(allow_historical=allow_historical, doc_ids=doc_ids)
        if eligible == 0:
            return self._result([], k, built)
        vector = self._provider.embed_query(text)
        self._conn.execute("select set_config('hnsw.iterative_scan', 'relaxed_order', true)")
        self._conn.execute("select set_config('hnsw.ef_search', %s, true)", (str(self._ef(k)),))
        params = {
            "q": vector_literal(vector),
            "v": built.embedding_version,
            "as_of": self._as_of or date.today(),
            "allow_historical": bool(allow_historical),
            "k": k,
            "doc_ids": list(doc_ids) if doc_ids else None,
        }
        rows = self._conn.execute(SEARCH_SQL, params).fetchall()
        page = sorted(((str(cid), float(dist)) for cid, dist in rows), key=lambda r: (r[1], r[0]))
        if len(page) != min(eligible, k):
            raise InfrastructureError(
                ErrorCode.internal_error,
                detail=f"vector page size {len(page)} != min(eligible={eligible}, k={k}); index scan starved under filters",
                retryable=False,
            )
        return self._result(page, k, built, exhausted=eligible < k)

    @staticmethod
    def _result(
        page: Sequence[tuple[str, float]], k: int, built: VectorVersions, *, exhausted: bool | None = None
    ) -> VectorSearchResult:
        candidates = tuple(
            Candidate(chunk_id=cid, raw_score=1.0 - dist, rank=rank) for rank, (cid, dist) in enumerate(page, start=1)
        )
        return VectorSearchResult(
            candidates=candidates,
            requested_k=k,
            returned_count=len(candidates),
            candidate_exhausted=(len(candidates) < k) if exhausted is None else exhausted,
            retriever_version=built.retriever_version,
            embedding_version=built.embedding_version,
            normalization_version=built.normalization_version,
        )

    def explain(self, query: str, k: int, *, allow_historical: bool = False) -> str:
        """EXPLAIN (json) of the search under the current role and settings; evidence for the plan chain."""
        import json

        require_identity(self._conn)
        vector = self._provider.embed_query(normalize_text(query))
        self._conn.execute("select set_config('hnsw.iterative_scan', 'relaxed_order', true)")
        self._conn.execute("select set_config('hnsw.ef_search', %s, true)", (str(self._ef(k)),))
        params = {
            "q": vector_literal(vector),
            "v": self._provider.spec.embedding_version,
            "as_of": self._as_of or date.today(),
            "allow_historical": bool(allow_historical),
            "k": k,
            "doc_ids": None,
        }
        row = self._conn.execute("explain (format json) " + SEARCH_SQL, params).fetchone()
        return json.dumps(row[0], ensure_ascii=False) if row else ""
