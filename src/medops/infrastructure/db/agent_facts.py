"""PV tool fact reads in one application-role transaction; no writes or elevated DSN.

final_check holds migration 0026's output fence until the caller stores the audit
and result and commits. Never keep this transaction open into the next planning call.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentFact
from medops.domain.agent_actions import AgentModel
from medops.domain.agent_execution import AgentContext, AgentSourceScope, AllowedSource
from medops.domain.common import Sha256
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.db.fact_plane import fact_plane_identity
from medops.infrastructure.db.final_output import (
    acquire_output_fence,
    directory_user,
    require_current_fact_transaction,
    require_same_user,
    validate_evidence,
)
from medops.retrieval.doc_focus import load_documents, norm
from medops.retrieval.integrity import database_identity
from medops.retrieval.recheck import recheck_candidates
from medops.retrieval.source_constraints import resolve_source_constraint

_SOURCE_SQL = """select d.doc_id::text, d.version, s.source_hash from documents d
join source_objects s on s.source_object_id=d.source_object_id
where d.doc_id=any(%(ids)s::uuid[]) and d.parse_quality='trusted' and s.integrity_status='verified'
and (d.status='active' or (%(historical)s and d.status='archived'))
and d.effective_from <= %(as_of)s and (d.effective_to is null or d.effective_to > %(as_of)s)"""


class FactDatabaseBinding(AgentModel):
    fact_database_id: UUID
    connection_identity: Sha256


def bind_fact_database(conn: Any) -> FactDatabaseBinding:
    """Trusted startup metadata read on the same admin/audit connection, never exposed as a tool.

    No DSN or privileged connection is passed to the action adapter. A PostgreSQL
    restart changes connection_identity and fails old runs until explicitly rebound.
    """
    return FactDatabaseBinding(
        fact_database_id=UUID(fact_plane_identity(conn)), connection_identity=database_identity(conn)
    )


class PgAgentFacts:
    def __init__(self, conn: Any, user: UserContext, *, database_binding: FactDatabaseBinding):
        self.conn: Any = DeadlineConnection(conn)
        self.user = user
        self.database_binding = FactDatabaseBinding.model_validate(database_binding.model_dump(mode="python"))

    def _identity(self, user: UserContext) -> None:
        require_current_fact_transaction(self.conn)
        if database_identity(self.conn) != self.database_binding.connection_identity:
            raise AgentToolFault("dependency_error")
        if user != self.user or not user.has_scopes((f"{user.dept.value}:read",)):
            raise AgentToolFault("denied_or_unavailable")
        row = self.conn.execute("select current_setting('medops.dept',true)").fetchone()
        if row is None or row[0] != user.dept.value:
            raise AgentToolFault("denied_or_unavailable")
        require_same_user(user, directory_user(self.conn, user))

    def check(self, context: AgentContext) -> None:
        self._identity(context.principal)
        if context.versions.fact_database_id != self.database_binding.fact_database_id:
            raise AgentToolFault("dependency_error")

    def _source_rows(self, ids: tuple[str, ...], context: QueryContext) -> tuple[AllowedSource, ...]:
        try:
            canonical = [str(UUID(i)) for i in ids]
        except (ValueError, TypeError, AttributeError):
            raise AgentToolFault("dependency_error") from None
        rows = self.conn.execute(
            _SOURCE_SQL, {"ids": canonical, "historical": context.historical_requested, "as_of": context.as_of}
        ).fetchall()
        return tuple(AllowedSource(doc_id=r[0], version=r[1], source_sha256=r[2]) for r in rows)

    def sources(self, context: AgentContext) -> None:
        self.check(context)
        if context.source_scope.resolution != "resolved":
            raise AgentToolFault(
                "ambiguous" if context.source_scope.resolution == "ambiguous" else "denied_or_unavailable"
            )
        expected = context.source_scope.allowed_sources
        fresh = self._source_rows(tuple(s.doc_id for s in expected), context.query_context)
        if set(fresh) != set(expected):
            raise AgentToolFault("denied_or_unavailable")

    def resolve_scope(
        self, requested_document: str, requested_version: str | None, *, query_context: QueryContext
    ) -> AgentSourceScope:
        """Resolve only visible sources, independently of a model's rewritten search query."""
        self._identity(self.user)
        documents = load_documents(
            self.conn, as_of=query_context.as_of, allow_historical=query_context.historical_requested
        )
        exact = [d for d in documents if d.doc_id == requested_document or norm(d.title) == norm(requested_document)]
        if exact:
            selected = tuple(d.doc_id for d in exact)
        else:
            constraint = resolve_source_constraint(requested_document, documents)
            selected = constraint.document_ids if constraint.required else ()
        rows = self._source_rows(selected, query_context) if selected else ()
        if requested_version is not None:
            rows = tuple(s for s in rows if s.version == requested_version)
        resolution: Literal["resolved", "ambiguous", "denied_or_unavailable"] = (
            "resolved" if len(rows) == 1 else "ambiguous" if rows else "denied_or_unavailable"
        )
        return AgentSourceScope(
            requested_document=requested_document,
            requested_version=requested_version,
            resolution=resolution,
            allowed_sources=rows if resolution == "resolved" else (),
        )

    def lookup(self, context: AgentContext, chunk_ids: tuple[str, ...]) -> tuple[AgentFact, ...]:
        self.sources(context)
        if len(set(chunk_ids)) != len(chunk_ids) or len(chunk_ids) > 64:
            raise AgentToolFault("dependency_error")
        if not chunk_ids:
            return ()
        result = recheck_candidates(
            self.conn,
            chunk_ids,
            as_of=context.query_context.as_of,
            allow_historical=context.query_context.historical_requested,
        )
        if result.rejected or len(result.evidence) != len(chunk_ids):
            raise AgentToolFault("denied_or_unavailable")
        sources = {s.doc_id: s for s in context.source_scope.allowed_sources}
        facts = []
        for evidence in result.evidence:
            source = sources.get(evidence.citation.doc_id)
            if source is None or source.version != evidence.citation.version:
                raise AgentToolFault("denied_or_unavailable")
            facts.append(AgentFact(evidence=evidence, source_sha256=source.source_sha256))
        return tuple(facts)

    def read(
        self, context: AgentContext, evidence: Evidence, region: Literal["current", "previous", "next"]
    ) -> AgentFact | None:
        current = self.lookup(context, (evidence.citation.chunk_id,))
        if len(current) != 1 or current[0].evidence != evidence:
            raise AgentToolFault("denied_or_unavailable")
        if region == "current":
            return current[0]
        # Only these server-owned SQL operators vary; no caller text is interpolated.
        if region == "previous":
            sql = "select b.chunk_id::text from chunks a join chunks b on b.doc_id=a.doc_id and b.seq<a.seq where a.chunk_id=%s order by b.seq desc limit 1"
        elif region == "next":
            sql = "select b.chunk_id::text from chunks a join chunks b on b.doc_id=a.doc_id and b.seq>a.seq where a.chunk_id=%s order by b.seq asc limit 1"
        else:
            raise AgentToolFault("unsupported")
        row = self.conn.execute(sql, (evidence.citation.chunk_id,)).fetchone()
        return self.lookup(context, (row[0],))[0] if row else None

    def final_check(self, context: AgentContext, facts: tuple[AgentFact, ...], *, check_sources: bool = True) -> None:
        acquire_output_fence(self.conn)
        self.check(context)
        if check_sources:
            self.sources(context)
        if facts:
            validate_evidence(self.conn, tuple(f.evidence for f in facts), context.query_context)
            current = self.lookup(context, tuple(f.evidence.citation.chunk_id for f in facts))
            if current != facts:
                raise AgentToolFault("denied_or_unavailable")
