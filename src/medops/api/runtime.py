"""Production wiring for the API (M3-01/05/12): PostgreSQL under the application role with one transaction per
request, the principal directory, the production retrieval stack pinned to one model thread, the OpenAI gateway
behind the monthly budget, the operation-key ledger, and the pinned production model configuration."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import psycopg

from medops.api.app import ApiRuntime
from medops.api.auth import Authenticator, JwtVerifier, PgDirectory, RemoteJwks
from medops.api.contracts import AskRequest
from medops.application.audit import TraceStore
from medops.application.metrics import MetricsSource, PgMetricsSource
from medops.application.tasks import TaskStore
from medops.core.config import Settings
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.executions import PgExecutionStore
from medops.harness.nodes import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL, production_model_config_version
from medops.harness.retrieval_port import ProductionRetrieval
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.documents import PgDocumentAdminStore
from medops.infrastructure.db.idempotency import PgReceiptStore
from medops.infrastructure.db.policies import PgPolicyStore
from medops.infrastructure.db.tasks import PgTaskStore
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.gateway import OPENAI_PRICES, ModelGateway, PriceTable
from medops.infrastructure.llm.meter import MeteredGateway
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway
from medops.ingestion import acl as acl_ops
from medops.ingestion import activate as activation
from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_lexical_retriever,
    production_lexical_versions,
    production_vector_retriever,
)
from medops.skills.catalog import default_registry
from medops.skills.production import doc_type_lookup, evidence_lookup
from medops.skills.registry import SkillContext

POLICY_VERSION = "policy-m3-api-1"  # released policy records arrive with M4; until then one pinned constant


def authenticator_from_settings(settings: Settings) -> Authenticator:
    """Keys come from `OIDC_JWKS_JSON` (static) or from the issuer (discovery / `OIDC_JWKS_URL`); the pseudonym key
    and issuer/audience are always required (ADR-0001)."""
    missing = [k for k in ("oidc_issuer", "oidc_audience", "identity_pseudonym_key") if getattr(settings, k) is None]
    if missing:
        raise ValueError(f"API identity boundary needs {', '.join(missing)} (ADR-0001)")
    assert settings.oidc_issuer and settings.oidc_audience and settings.identity_pseudonym_key
    if settings.oidc_jwks_json:
        verifier = JwtVerifier(
            issuer=settings.oidc_issuer, audience=settings.oidc_audience, jwks=json.loads(settings.oidc_jwks_json)
        )
    else:
        verifier = JwtVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            key_source=RemoteJwks(settings.oidc_issuer, jwks_url=settings.oidc_jwks_url),
        )
    groups = json.loads(settings.oidc_group_scopes_json) if settings.oidc_group_scopes_json else {}
    return Authenticator(
        verifier=verifier,
        pseudonym_key=settings.identity_pseudonym_key.get_secret_value().encode("utf-8"),
        group_scopes={str(k): [str(x) for x in v] for k, v in groups.items()},
    )


@dataclass
class ProductionRuntime:
    """Built once per process; `connection()` opens a fresh application-role connection per request."""

    settings: Settings
    authenticator: Authenticator
    gateway: ModelGateway
    embedding: Any
    reranker: Any
    versions: VersionSet
    as_of: date | None = None
    _dsn: str = field(default="", repr=False)
    _admin_dsn: str | None = field(default=None, repr=False)

    @classmethod
    def from_settings(
        cls, settings: Settings, *, device: str = "cpu", pinned_timeout_s: float = 120.0
    ) -> ProductionRuntime:
        from medops.retrieval.rerank import BgeRerankerV2M3
        from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

        pinned = PinnedThread(pinned_timeout_s)
        embedding = PinnedEmbedding(pinned.call(lambda: BgeM3EmbeddingProvider(device=device)), pinned)
        reranker = PinnedReranker(pinned.call(lambda: BgeRerankerV2M3(device=device, output=RERANK_OUTPUT)), pinned)
        gateway = BudgetedGateway(
            OpenAIModelGateway.from_settings(settings),
            prices=PriceTable(OPENAI_PRICES),
            ledger=InMemorySpendLedger(),
            monthly_cap_usd=settings.llm_monthly_budget_usd,
        )
        versions = VersionSet(
            policy_version=POLICY_VERSION,
            retrieval_version=PRODUCTION_RETRIEVAL_VERSION,
            skill_version_set=default_registry().version_set(),
            model_config_version=production_model_config_version(),
        )
        runtime = cls(
            settings=settings,
            authenticator=authenticator_from_settings(settings),
            gateway=gateway,
            embedding=embedding,
            reranker=reranker,
            versions=versions,
        )
        runtime._dsn = settings.database_url.get_secret_value()
        runtime._admin_dsn = settings.database_admin_url.get_secret_value() if settings.database_admin_url else None
        return runtime

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        with psycopg.connect(self._dsn) as conn:
            with conn.transaction():
                yield conn

    def directory(self, conn: Any) -> PgDirectory:
        return PgDirectory(conn)

    @contextmanager
    def admin_connection(self) -> Iterator[psycopg.Connection[Any]]:
        """Admin routes (M3-03) run on the admin role: DATABASE_ADMIN_URL is required for them (INV-AUTH-05)."""
        if not self._admin_dsn:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail="DATABASE_ADMIN_URL is not configured", retryable=False
            )
        with psycopg.connect(self._admin_dsn) as conn:
            with conn.transaction():
                yield conn

    def document_admin(self, conn: Any) -> tuple[PgDocumentAdminStore, PgDocumentActions]:
        return PgDocumentAdminStore(conn), PgDocumentActions(conn)

    def policy_store(self, conn: Any) -> PgPolicyStore:
        return PgPolicyStore(conn)

    def receipt_store(self, conn: Any) -> PgReceiptStore:
        return PgReceiptStore(conn)

    def bind_identity(self, conn: Any, user: UserContext) -> None:
        conn.execute(
            "select set_config('medops.dept', %s, true)", (user.dept.value,)
        )  # transaction-local (baseline 3.7)

    def build_deps(self, conn: Any, user: UserContext, request: AskRequest) -> HarnessDeps:
        as_of = request.historical.as_of if request.historical is not None else self.as_of

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn  # already inside the request transaction with the department injected

        retrieval = ProductionRetrieval(
            conn_for_user=conn_for_user,
            lexical_factory=lambda c: production_lexical_retriever(c, as_of=as_of),
            vector_factory=lambda c: production_vector_retriever(c, self.embedding, as_of=as_of),
            reranker=self.reranker,
            config=production_hybrid_config(),
            lexical_versions=production_lexical_versions(),
        )
        return HarnessDeps(
            retrieval=retrieval,
            gateway=MeteredGateway(self.gateway),  # per-request calls/tokens/cost for the trace
            answer_model_id=PRODUCTION_ANSWER_MODEL,
            judge_model_id=PRODUCTION_JUDGE_MODEL,
            as_of=as_of,
            executions=PgExecutionStore(conn),
        )

    def task_store(self, conn: Any) -> TaskStore:
        return PgTaskStore(conn)

    def trace_store(self, conn: Any) -> TraceStore:
        return PgTraceStore(conn)

    def metrics_source(self, conn: Any) -> MetricsSource:
        return PgMetricsSource(conn)

    @property
    def monthly_cap_usd(self) -> float | None:
        return self.settings.llm_monthly_budget_usd

    # ---- worker environment (medops.application.tasks.WorkerEnvironment)
    def resolve_user(self, conn: Any, principal: str) -> UserContext | None:
        p = PgDirectory(conn).resolve(principal) if len(principal) == 64 else None
        if p is None or not p.active:
            return None
        return UserContext(user_id=principal, dept=p.dept, roles=p.roles, acl_scopes=p.scopes)

    def skill_context(
        self, conn: Any, user: UserContext, trace_id: str, historical: Mapping[str, Any] | None
    ) -> SkillContext:
        as_of = date.fromisoformat(historical["as_of"]) if historical and historical.get("as_of") else self.as_of
        request = AskRequest(query="task", historical=None)
        deps = self.build_deps(conn, user, request)

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn

        return SkillContext(
            user=user,
            versions=self.versions,
            deps=deps,
            evidence_lookup=evidence_lookup(conn_for_user, as_of=as_of),
            doc_type_lookup=doc_type_lookup(conn_for_user),
            trace_id=trace_id,
            run_id=trace_id,
            as_of=as_of,
        )

    def ready(self) -> bool:
        try:
            with psycopg.connect(self._dsn, connect_timeout=2) as conn:
                conn.execute("select 1").fetchone()
            return True
        except psycopg.Error:
            return False


def _check_protocol(runtime: ProductionRuntime) -> ApiRuntime:  # structural conformance, checked by mypy
    return runtime


class PgDocumentActions:
    """The publish chain bound to an admin connection (ingestion.activate / ingestion.acl)."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def activate(self, document_key: str, effective_from: Any, *, actor: str, reason: str) -> None:
        activation.activate_document(self._conn, document_key, effective_from, actor=actor, reason=reason)

    def archive(self, document_key: str, effective_to: Any, *, actor: str, reason: str) -> None:
        activation.archive_document(self._conn, document_key, effective_to, actor=actor, reason=reason)

    def withdraw(self, document_key: str, *, actor: str, reason: str) -> None:
        activation.withdraw_document(self._conn, document_key, actor=actor, reason=reason)

    def change_acl(
        self, document_key: str, *, grant: Sequence[str], revoke: Sequence[str], actor: str, reason: str
    ) -> Mapping[str, Any]:
        change = acl_ops.change_acl(self._conn, document_key, grant=grant, revoke=revoke, actor=actor, reason=reason)
        return {"granted": change.granted, "revoked": change.revoked, "read_depts": change.read_depts}
