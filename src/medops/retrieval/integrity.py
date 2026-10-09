"""Read-only production index health and transactional-outbox backlog (OPT-15)."""

from __future__ import annotations

from typing import Any

import psycopg

from medops.core.canonical import canonical_hash
from medops.core.errors import InfrastructureError
from medops.retrieval.lexical.pg_lexical_common import read_built_versions
from medops.retrieval.maintenance import CONSUMERS
from medops.retrieval.production import (
    PRODUCTION_LEXICAL_INDEX_NAME,
    IndexCoverageError,
    index_coverage,
    production_lexical_versions,
    require_production_lexical_runtime,
)
from medops.retrieval.vector.embedding import (
    BGE_M3_MODEL_ID,
    BGE_M3_REVISION,
    DIMENSION,
    EMBEDDING_FIELDS,
    EMBEDDING_VERSION,
    MAX_SEQ_LENGTH,
    EmbeddingSpec,
)
from medops.retrieval.vector.pg_vector import read_meta

OUTBOX_CRITICAL_LAG_S = 300
READINESS_CONSUMERS = frozenset({"lexical-index", "vector-index"})


def database_identity(conn: psycopg.Connection[Any]) -> str:
    """The same database of the same running cluster, whichever address or socket each DSN uses: database name
    and OID plus the postmaster start time (an address-based identity reported a false mismatch when the app and
    admin DSNs reached one server by different routes, record 144). Nothing here names a host or a DSN."""
    row = conn.execute(
        "select current_database(), (select oid from pg_database where datname = current_database())::text, "
        "extract(epoch from pg_postmaster_start_time())::bigint"
    ).fetchone()
    if row is None:
        raise ValueError("database identity unavailable")
    return canonical_hash(list(row))


def has_global_view(conn: psycopg.Connection[Any]) -> bool:
    """Whether the connection's role sees every row (superuser, RLS bypass or the admin role): the precondition of any
    corpus-wide statement, since an RLS-filtered view looks like a healthy but smaller index."""
    row = conn.execute(
        "select rolsuper or rolbypassrls or pg_has_role(current_user, 'medops_admin_role', 'member') "
        "from pg_roles where rolname=current_user"
    ).fetchone()
    return bool(row and row[0])


def inspect_readiness(dsn: str, *, embedding: EmbeddingSpec | None = None) -> dict[str, Any]:
    """`inspect_retrieval` on a bounded, read-only snapshot connection of its own (the ops endpoint and the CLI)."""
    with psycopg.connect(dsn, connect_timeout=2, options="-c statement_timeout=1000") as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        return inspect_retrieval(conn, embedding=embedding)


def inspect_retrieval(conn: psycopg.Connection[Any], *, embedding: EmbeddingSpec | None = None) -> dict[str, Any]:
    """Global coverage needs a role that can see all documents; an RLS-empty view is not a healthy index.

    Caller supplies a read-only transaction and statement timeout. No models are loaded or called.
    Unacked events are monitored independently: already-built indexes can be complete despite old acks.
    """
    if not has_global_view(conn):
        raise ValueError("global index inspection requires the administrative visibility boundary")
    identity = database_identity(conn)
    coverage = index_coverage(conn)
    counts = conn.execute(
        "select count(*), count(*) filter (where not exists (select 1 from chunks c where c.doc_id=d.doc_id)) "
        "from documents d where d.status='active'"
    ).fetchone()
    assert counts is not None
    coverage.update(active_documents=int(counts[0]), active_documents_without_chunks=int(counts[1]))
    problems = []
    if not coverage["active_documents"] or not coverage["active_chunks"]:
        problems.append("empty_active_corpus")
    if coverage["active_documents_without_chunks"]:
        problems.append("active_document_without_chunks")
    if coverage["missing_lexical"]:
        problems.append("lexical_coverage_gap")
    if coverage["missing_embedding"]:
        problems.append("embedding_coverage_gap")
    try:
        require_production_lexical_runtime(conn)
        lexical_ok = read_built_versions(conn, PRODUCTION_LEXICAL_INDEX_NAME) == production_lexical_versions()
    except (InfrastructureError, ValueError):
        lexical_ok = False
    if not lexical_ok:
        problems.append("lexical_version_missing_or_mismatched")
    expected = (
        embedding.model_dump(include=EMBEDDING_FIELDS)
        if embedding
        else {
            "model_id": BGE_M3_MODEL_ID,
            "model_revision": BGE_M3_REVISION,
            "dimension": DIMENSION,
            "normalization": "l2",
            "max_seq_length": MAX_SEQ_LENGTH,
        }
    )
    try:
        built = read_meta(conn, EMBEDDING_VERSION)
        embedding_ok = built.model_dump(include=EMBEDDING_FIELDS) == expected
        if embedding and embedding.embedding_version != EMBEDDING_VERSION:
            embedding_ok = False
    except (InfrastructureError, ValueError):
        embedding_ok = False
    if not embedding_ok:
        problems.append("embedding_version_missing_or_mismatched")
    rows = conn.execute(
        """select c.name,
                  count(e.event_id) filter (where f.dead_lettered_at is null),
                  greatest(0, coalesce(extract(epoch from (now() - min(e.created_at)
                      filter (where f.dead_lettered_at is null))), 0)),
                  count(e.event_id) filter (where f.dead_lettered_at is not null)
           from unnest(%s::text[]) c(name)
           left join outbox_events e on not exists (
               select 1 from outbox_consumer_acks a where a.consumer=c.name and a.event_id=e.event_id)
           left join outbox_consumer_failures f on f.consumer=c.name and f.event_id=e.event_id
           group by c.name order by c.name""",
        (list(CONSUMERS),),
    ).fetchall()
    outbox_status = {
        r[0]: {"pending": int(r[1]), "oldest_age_s": float(r[2]), "dead_lettered": int(r[3])} for r in rows
    }
    outbox_blocks = any(
        name in READINESS_CONSUMERS
        and (item["dead_lettered"] or (item["pending"] and item["oldest_age_s"] > OUTBOX_CRITICAL_LAG_S))
        for name, item in outbox_status.items()
    )
    if any(name in READINESS_CONSUMERS and item["dead_lettered"] for name, item in outbox_status.items()):
        problems.append("outbox_dead_letter")
    if any(
        name in READINESS_CONSUMERS and item["pending"] and item["oldest_age_s"] > OUTBOX_CRITICAL_LAG_S
        for name, item in outbox_status.items()
    ):
        problems.append("outbox_critical_lag")
    return {
        "ready": not problems,
        "database": conn.info.dbname,
        "database_identity": identity,
        "coverage": coverage,
        "lexical_version_ok": lexical_ok,
        "embedding_version_ok": embedding_ok,
        "problems": problems,
        "outbox": outbox_status,
        "outbox_blocks_readiness": outbox_blocks,
    }


def require_retrieval_integrity(
    conn: psycopg.Connection[Any],
    *,
    plane: str,
    embedding: EmbeddingSpec | None = None,
    request_conn: psycopg.Connection[Any] | None = None,
) -> dict[str, Any]:
    """Production evaluation gate; the caller owns the read-only snapshot and bounded connection.

    This checks the production departmental-BM25/vector fact plane. An experimental lexical adapter still needs
    its own index/version/coverage proof in addition to this common prerequisite. Backlog is reported separately.
    """
    status = inspect_retrieval(conn, embedding=embedding)
    if request_conn is not None and database_identity(request_conn) != status["database_identity"]:
        status["problems"].append("request_and_admin_database_mismatch")
        status["ready"] = False
    if not status["ready"]:
        raise IndexCoverageError(f"{plane}: retrieval preflight failed: {', '.join(status['problems'])}")
    return status
