"""Production wiring for the API (M3-01/05/12): PostgreSQL under the application role with one transaction per
request, the principal directory, the production retrieval stack pinned to one model thread, the OpenAI gateway
behind the monthly budget, the operation-key ledger, and the pinned production model configuration."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import psycopg

from medops.api.auth import Authenticator, JwtVerifier, PgDirectory, RemoteJwks
from medops.api.contracts import AskRequest
from medops.api.ports import ApiRuntime
from medops.application.audit import TraceStore
from medops.application.metrics import MetricsSource, PgMetricsSource
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.policy_loader import (
    ReleasedPolicySet,
    ReleaseState,
    RequestPolicies,
    RoutedPolicies,
    load_release_state,
    load_released,
)
from medops.application.tasks import TaskStore
from medops.core.config import Settings
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.assembly import build_retrieval
from medops.harness.dependencies import HarnessDeps
from medops.harness.executions import PgExecutionStore
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL, production_model_config_version
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.documents import PgDocumentAdminStore
from medops.infrastructure.db.idempotency import PgReceiptStore
from medops.infrastructure.db.payloads import PgPayloadStore
from medops.infrastructure.db.policies import PgPolicyStore
from medops.infrastructure.db.tasks import PgTaskStore
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.gateway import ModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.ingestion import acl as acl_ops
from medops.ingestion import activate as activation
from medops.retrieval.doc_focus import load_titles
from medops.retrieval.hybrid import HybridConfig
from medops.retrieval.integrity import database_identity, inspect_readiness
from medops.retrieval.pinned import PinnedEmbedding, PinnedReranker, PinnedThread
from medops.retrieval.production import (
    PRODUCTION_RETRIEVAL_VERSION,
    RERANK_OUTPUT,
    production_hybrid_config,
    production_retrieval_inputs,
)
from medops.retrieval.query_translation import QUERY_TRANSLATION_OFF, QueryTranslator
from medops.retrieval.versioning import compute_retrieval_version
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


def open_connection(dsn: str, settings: Any) -> psycopg.Connection[Any]:
    """Every runtime connection fails fast (record 78): a connect timeout and a per-statement timeout, and an
    unreachable database is `dependency_unavailable` (503, retryable) rather than a request that hangs until the
    client gives up."""
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=settings.db_connect_timeout_s,
            options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
        )
    except psycopg.OperationalError as exc:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable, detail=f"database: {type(exc).__name__}", retryable=True
        ) from None


def retrieval_cache_from_settings(settings: Settings) -> Any:
    """The retrieval candidate cache the settings ask for, or None (`retrieval_cache = off`, the default)."""
    from medops.retrieval.runtime import candidate_cache_from_settings

    return candidate_cache_from_settings(settings)


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
    _restricted_dsn: str | None = field(default=None, repr=False)
    _key_provider: Any = field(default=None, repr=False)
    policies: ReleasedPolicySet = field(default_factory=ReleasedPolicySet.empty)  # what production applies (M4-03)
    _hybrid: HybridConfig | None = field(default=None, repr=False)
    _state_cache: tuple[float, ReleaseState] | None = field(default=None, repr=False)  # TTL re-read (M4-09)
    _rerankers: dict[int, Any] = field(default_factory=dict, repr=False)  # one reranker per released output size
    _glossaries: dict[str, Any] = field(default_factory=dict, repr=False)  # verified glossaries by released version
    _retrieval_cache: Any = field(default=None, repr=False)  # CandidateCache when `retrieval_cache` is not off
    _pinned: Any = field(default=None, repr=False)
    _device: str = field(default="cpu", repr=False)
    _integrity_cache: tuple[float, dict[str, Any]] | None = field(default=None, repr=False)
    _integrity_lock: Any = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(
        cls, settings: Settings, *, device: str = "cpu", pinned_timeout_s: float = 120.0
    ) -> ProductionRuntime:
        from medops.retrieval.rerank import BgeRerankerV2M3
        from medops.retrieval.vector.embedding import BgeM3EmbeddingProvider

        dsn = settings.database_url.get_secret_value()
        with open_connection(dsn, settings) as conn, conn.transaction():
            released = load_released(
                conn
            )  # INV-HAR-06: production applies the released pointers, never the repo's latest text
        hybrid = released.hybrid_config(production_hybrid_config())
        rerank_output = released.rerank_output(RERANK_OUTPUT)
        glossary_version = released.glossary_version()
        multi_query = released.multi_query()
        doc_focus = released.doc_focus()
        source_constraint = released.source_constraint()
        query_translation = released.query_translation()
        pinned = PinnedThread(pinned_timeout_s)
        embedding = PinnedEmbedding(pinned.call(lambda: BgeM3EmbeddingProvider(device=device)), pinned)
        reranker = PinnedReranker(pinned.call(lambda: BgeRerankerV2M3(device=device, output=rerank_output)), pinned)
        gateway = build_budgeted_gateway(settings)
        retrieval_version = (
            compute_retrieval_version(
                production_retrieval_inputs(
                    hybrid,
                    rerank_output=rerank_output,
                    glossary_version=glossary_version,
                    multi_query=multi_query,
                    doc_focus=doc_focus,
                    source_constraint=source_constraint,
                    query_translation=query_translation,
                )
            )
            if released.retrieval_overridden()
            else PRODUCTION_RETRIEVAL_VERSION
        )
        versions = VersionSet(
            policy_version=released.policy_version(POLICY_VERSION),
            retrieval_version=retrieval_version,
            skill_version_set=default_registry().version_set(),
            model_config_version=production_model_config_version() + released.model_config_suffix(),
        )
        runtime = cls(
            settings=settings,
            authenticator=authenticator_from_settings(settings),
            gateway=gateway,
            embedding=embedding,
            reranker=reranker,
            versions=versions,
        )
        runtime._dsn = dsn
        runtime.policies = released
        runtime._hybrid = hybrid
        runtime._pinned = pinned
        runtime._device = device
        runtime._rerankers = {rerank_output: reranker}
        runtime.glossary_for(glossary_version)  # fail fast: a released glossary must be present and verified at start
        runtime._retrieval_cache = retrieval_cache_from_settings(settings)
        runtime._admin_dsn = settings.database_admin_url.get_secret_value() if settings.database_admin_url else None
        runtime._restricted_dsn = (
            settings.database_restricted_url.get_secret_value() if settings.database_restricted_url else None
        )
        if settings.payload_key_file:
            from medops.core.envelope import LocalFileKeyProvider

            runtime._key_provider = LocalFileKeyProvider(settings.payload_key_file)
        return runtime

    def _open(self, dsn: str) -> psycopg.Connection[Any]:
        return open_connection(dsn, self.settings)

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection[Any]]:
        with self._open(self._dsn) as conn:
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
        with self._open(self._admin_dsn) as conn:
            with conn.transaction():
                yield conn

    def document_admin(self, conn: Any) -> tuple[PgDocumentAdminStore, PgDocumentActions]:
        return PgDocumentAdminStore(conn), PgDocumentActions(conn)

    def policy_store(self, conn: Any) -> PgPolicyStore:
        return PgPolicyStore(conn)

    def receipt_store(self, conn: Any) -> PgReceiptStore:
        return PgReceiptStore(conn)

    def payload_writer(self, conn: Any) -> PayloadWriter | None:
        """None when no key file is configured: traces are still written, replay payloads are not (dev default)."""
        if self._key_provider is None:
            return None
        return PayloadWriter(
            store=PgPayloadStore(conn), provider=self._key_provider, retention_days=self.settings.payload_retention_days
        )

    @contextmanager
    def restricted_connection(self) -> Iterator[psycopg.Connection[Any]]:
        if not self._restricted_dsn or self._key_provider is None:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable,
                detail="DATABASE_RESTRICTED_URL / PAYLOAD_KEY_FILE not configured",
                retryable=False,
            )
        with self._open(self._restricted_dsn) as conn:
            with conn.transaction():
                yield conn

    def payload_reader(self, conn: Any) -> PayloadReader:
        return PayloadReader(store=PgPayloadStore(conn), provider=self._key_provider)

    def bind_identity(self, conn: Any, user: UserContext) -> None:
        conn.execute(
            "select set_config('medops.dept', %s, true)", (user.dept.value,)
        )  # transaction-local (baseline 3.7)

    # ---- released policy per request (M4-09: canary split, rollback without restart)
    @property
    def observation_window(self) -> timedelta:
        return timedelta(hours=float(getattr(self.settings, "observation_window_hours", 24.0)))

    @property
    def allow_drill(self) -> bool:
        return getattr(getattr(self.settings, "app_env", None), "value", None) == "dev"

    def release_state(self, conn: Any) -> ReleaseState:
        """The released pointers with their canary state, re-read at most every `policy_reload_ttl_s` seconds."""
        ttl = float(getattr(self.settings, "policy_reload_ttl_s", 5.0))
        now = time.monotonic()
        if self._state_cache is not None and now - self._state_cache[0] < ttl:
            return self._state_cache[1]
        state = load_release_state(conn)
        self._state_cache = (now, state)
        return state

    def request_policies(self, routed: RoutedPolicies) -> RequestPolicies:
        pol = routed.policies
        hybrid = pol.hybrid_config(production_hybrid_config())
        rerank_output = pol.rerank_output(RERANK_OUTPUT)
        retrieval_version = (
            compute_retrieval_version(
                production_retrieval_inputs(
                    hybrid,
                    rerank_output=rerank_output,
                    glossary_version=pol.glossary_version(),
                    multi_query=pol.multi_query(),
                    doc_focus=pol.doc_focus(),
                    source_constraint=pol.source_constraint(),
                    query_translation=pol.query_translation(),
                )
            )
            if pol.retrieval_overridden()
            else PRODUCTION_RETRIEVAL_VERSION
        )
        versions = VersionSet(
            policy_version=routed.policy_version(POLICY_VERSION),
            retrieval_version=retrieval_version,
            skill_version_set=self.versions.skill_version_set,
            model_config_version=production_model_config_version() + pol.model_config_suffix(),
        )
        return RequestPolicies(policies=pol, versions=versions, canary_ids=routed.canary_ids)

    def route_policies(self, conn: Any, user: UserContext) -> RequestPolicies:
        """Stable per-principal split across every canary; the versions name exactly what this request runs under."""
        return self.request_policies(self.release_state(conn).for_principal(user.user_id))

    def reranker_for(self, output: int) -> Any:
        if output not in self._rerankers:
            if self._pinned is None:
                return self.reranker
            from medops.retrieval.pinned import PinnedReranker
            from medops.retrieval.rerank import BgeRerankerV2M3

            pinned, device = self._pinned, self._device
            self._rerankers[output] = PinnedReranker(
                pinned.call(lambda: BgeRerankerV2M3(device=device, output=output)), pinned
            )
        return self._rerankers[output]

    def glossary_for(self, version: str) -> Any:
        """The verified glossary a released version names (None for `glossary-none`); cached per version."""
        from medops.retrieval.glossary_store import load_versioned_glossary
        from medops.retrieval.rewrite import GLOSSARY_NONE

        if version == GLOSSARY_NONE:
            return None
        if version not in self._glossaries:
            self._glossaries[version] = load_versioned_glossary(getattr(self.settings, "glossary_dir", None), version)
        return self._glossaries[version]

    def build_deps(
        self, conn: Any, user: UserContext, request: AskRequest, routed: RequestPolicies | None = None
    ) -> HarnessDeps:
        as_of = request.historical.as_of if request.historical is not None else self.as_of
        routed = routed or self.route_policies(conn, user)
        hybrid = routed.policies.hybrid_config(production_hybrid_config())
        reranker = self.reranker_for(routed.policies.rerank_output(RERANK_OUTPUT))

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn  # already inside the request transaction with the department injected

        metered = MeteredGateway(self.gateway)  # per-request calls/tokens/cost for the trace, translation included
        qt_model = routed.policies.query_translation()
        translator = QueryTranslator(metered, qt_model).translate if qt_model != QUERY_TRANSLATION_OFF else None
        retrieval = build_retrieval(
            conn_for_user=conn_for_user,
            as_of=as_of,
            provider=self.embedding,
            reranker=reranker,
            config=hybrid,
            glossary=self.glossary_for(routed.policies.glossary_version()),
            multi_query=routed.policies.multi_query(),
            doc_focus=routed.policies.doc_focus(),
            source_constraint=routed.policies.source_constraint(),
            translator=translator,
            cache=self._retrieval_cache,
            cache_versions=(
                (routed.versions.retrieval_version, routed.versions.policy_version) if self._retrieval_cache else None
            ),
        )
        return HarnessDeps(
            retrieval=retrieval,
            answer_system=routed.policies.answer_system(ANSWER_SYSTEM),
            evidence_focus=routed.policies.evidence_focus(),
            sentence_scorer=reranker.score,
            doc_titles=lambda _user, ids: load_titles(conn, ids),  # the request connection: department-scoped
            gateway=metered,
            answer_model_id=PRODUCTION_ANSWER_MODEL,
            answer_model_by_intent=routed.policies.answer_models(),
            judge_model_id=PRODUCTION_JUDGE_MODEL,
            as_of=as_of,
            executions=PgExecutionStore(conn),
        )

    def task_store(self, conn: Any) -> TaskStore:
        return PgTaskStore(conn)

    def trace_store(self, conn: Any) -> TraceStore:
        return PgTraceStore(conn)

    def metrics_source(self, conn: Any) -> MetricsSource:
        return PgMetricsSource(conn, retrieval_integrity=self.retrieval_integrity)

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
        routed = self.route_policies(conn, user)
        deps = self.build_deps(conn, user, request, routed)

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn

        return SkillContext(
            user=user,
            versions=routed.versions,
            deps=deps,
            evidence_lookup=evidence_lookup(conn_for_user, as_of=as_of),
            doc_type_lookup=doc_type_lookup(conn_for_user),
            trace_id=trace_id,
            run_id=trace_id,
            as_of=as_of,
        )

    def retrieval_integrity(self) -> dict[str, Any]:
        """A bounded, five-second status cache; only aggregate metrics leave the ops endpoint."""
        with self._integrity_lock:
            now = time.monotonic()
            if self._integrity_cache and now - self._integrity_cache[0] < 5.0:
                return self._integrity_cache[1]
            if not self._admin_dsn:
                status: dict[str, Any] = {"ready": False, "problems": ["integrity_connection_not_configured"]}
            else:
                try:
                    status = inspect_readiness(
                        self._admin_dsn,
                        embedding=self.embedding.spec,
                        cache_required=getattr(self.settings, "retrieval_cache", "off") == "redis",
                    )
                except (psycopg.Error, InfrastructureError, ValueError):
                    status = {"ready": False, "problems": ["integrity_check_unavailable"]}
            self._integrity_cache = (time.monotonic(), status)
            return status

    def ready(self) -> bool:
        if self._pinned is not None and self._pinned.stalled:
            return False
        status = self.retrieval_integrity()
        if not status["ready"]:
            return False
        try:
            with psycopg.connect(self._dsn, connect_timeout=2, options="-c statement_timeout=1000") as conn:
                return database_identity(conn) == status["database_identity"]
        except (psycopg.Error, ValueError):
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
