"""Shared production wiring for API and task workers (M3-01/05/12): PostgreSQL under the application role with one transaction per
request, the principal directory, the production retrieval stack pinned to one model thread, the OpenAI gateway
behind the monthly budget, the operation-key ledger, and the pinned production model configuration."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import psycopg

from medops.application.audit import TraceStore
from medops.application.contracts import AskRequest, HistoricalRequest
from medops.application.metrics import MetricsSource, PgMetricsSource
from medops.application.output_binding import EvidenceBinding, EvidenceLookupBinding, LookupBinding
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.policy_loader import (
    ReleasedPolicySet,
    RequestPolicies,
    RoutedPolicies,
    load_released,
)
from medops.application.tasks import TaskRecord, TaskStore
from medops.bootstrap.connections import open_connection
from medops.bootstrap.identity import authenticator_from_settings
from medops.bootstrap.policies import PolicyRouter, request_policies
from medops.bootstrap.retrieval import RetrievalServices, execution_binding
from medops.core.config import Settings
from medops.core.deadline import deadline_scope
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext, resolve_query_context
from medops.domain.state import VersionSet
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.dependencies import HarnessDeps
from medops.harness.executions import PgExecutionStore
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.db.documents import PgDocumentAdminStore
from medops.infrastructure.db.final_output import (
    acquire_admin_write_fence,
    acquire_output_fence,
    directory_user,
    require_read_committed_transaction,
    require_same_user,
    validate_evidence,
)
from medops.infrastructure.db.idempotency import PgReceiptStore
from medops.infrastructure.db.payloads import PgPayloadStore
from medops.infrastructure.db.policies import PgPolicyStore
from medops.infrastructure.db.tasks import PgTaskStore
from medops.infrastructure.identity import Authenticator, PgDirectory
from medops.infrastructure.llm.execution_budget import configured_limits
from medops.infrastructure.llm.factory import build_budgeted_gateway
from medops.infrastructure.llm.gateway import ModelGateway
from medops.infrastructure.llm.meter import MeteredGateway
from medops.ingestion import acl as acl_ops
from medops.ingestion import activate as activation
from medops.retrieval.doc_focus import load_titles
from medops.retrieval.inference_process import InferenceProcess, ProcessEmbedding, ProcessReranker
from medops.retrieval.integrity import database_identity, inspect_readiness
from medops.retrieval.production import (
    RERANK_OUTPUT,
)
from medops.retrieval.recheck import recheck_candidates
from medops.retrieval.runtime import candidate_cache_from_settings
from medops.skills.catalog import default_registry
from medops.skills.production import doc_type_lookup, evidence_lookup
from medops.skills.registry import SkillContext


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
    _retrieval_services: RetrievalServices | None = field(default=None, repr=False)
    _policy_router: PolicyRouter | None = field(default=None, repr=False)
    _pinned: Any = field(default=None, repr=False)
    _device: str = field(default="cpu", repr=False)
    _integrity_cache: tuple[float, dict[str, Any]] | None = field(default=None, repr=False)
    _integrity_lock: Any = field(default_factory=threading.Lock, repr=False)
    _composition_lock: Any = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(
        cls, settings: Settings, *, device: str = "cpu", pinned_timeout_s: float = 120.0
    ) -> ProductionRuntime:
        dsn = settings.database_url.get_secret_value()
        with open_connection(dsn, settings) as conn, conn.transaction():
            released = load_released(
                conn
            )  # INV-HAR-06: production applies the released pointers, never the repo's latest text
        rerank_output = released.rerank_output(RERANK_OUTPUT)
        pinned = InferenceProcess(device=device, output=rerank_output, timeout_s=pinned_timeout_s)
        gateway = None
        try:
            embedding = ProcessEmbedding(pinned)
            reranker = ProcessReranker(pinned, output=rerank_output)
            gateway = build_budgeted_gateway(settings, require_execution_budget=True)
            versions = request_policies(RoutedPolicies(released), default_registry().version_set()).versions
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
            runtime._pinned = pinned
            runtime._device = device
            runtime._retrieval_services = RetrievalServices(
                settings, embedding, reranker, pinned=pinned, cache=candidate_cache_from_settings(settings)
            )
            runtime.retrieval_services.glossary_for(released.glossary_version())  # Fail fast on missing released data.
            runtime._admin_dsn = settings.database_admin_url.get_secret_value() if settings.database_admin_url else None
            runtime._restricted_dsn = (
                settings.database_restricted_url.get_secret_value() if settings.database_restricted_url else None
            )
            if settings.payload_key_file:
                from medops.core.envelope import LocalFileKeyProvider

                runtime._key_provider = LocalFileKeyProvider(settings.payload_key_file)
            return runtime
        except BaseException:
            pinned.close()
            if gateway is not None:
                gateway.close()
            raise

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

    def validate_privileged_access(
        self,
        identity_conn: Any,
        target_conn: Any,
        user: UserContext,
        *,
        authorization: str | None,
        mutation: bool = False,
    ) -> None:
        """Bind privileged work to current identity until the target transaction commits.

        Reads hold the app-role shared fence. Writes hold the exclusive fence on
        their own admin connection so statement triggers reacquire the same lock.
        No model work belongs inside this short privileged transaction.
        """
        try:
            with deadline_scope(5.0):
                identity = DeadlineConnection(identity_conn)
                target = DeadlineConnection(target_conn)
                require_read_committed_transaction(identity)
                require_read_committed_transaction(target)
                if mutation:
                    acquire_admin_write_fence(target)
                else:
                    acquire_output_fence(identity)
                if database_identity(identity) != database_identity(target):
                    raise BusinessError(ErrorCode.forbidden, "privileged work requires the identity database")
                current = self.authenticator.authenticate(authorization, self.directory(identity))
                require_same_user(user, current)
        except psycopg.Error as exc:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail=type(exc).__name__, retryable=False
            ) from None

    def validate_final_output(
        self,
        conn: Any,
        user: UserContext,
        evidence: Sequence[Evidence],
        context: QueryContext,
        *,
        authorization: str | None = None,
        lookups: Sequence[LookupBinding] = (),
    ) -> None:
        try:
            # A provider result is already in memory. A SQL failure must roll back
            # this check, not destroy the enclosing transaction's failure audit.
            with deadline_scope(5.0), conn.transaction():
                conn = DeadlineConnection(conn)
                acquire_output_fence(conn)
                current = (
                    self.authenticator.authenticate(authorization, self.directory(conn))
                    if authorization is not None
                    else directory_user(conn, user)
                )
                require_same_user(user, current)
                # Never bind a different department to salvage a changed identity.
                validate_evidence(conn, evidence, context)
                self._validate_lookups(conn, user, context, lookups)
        except psycopg.Error as exc:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail=type(exc).__name__, retryable=False
            ) from None

    def validate_task_result(
        self, conn: Any, user: UserContext, record: TaskRecord, *, authorization: str | None
    ) -> None:
        if record.result is None:
            return
        binding = record.output_binding
        if binding is None:
            raise BusinessError(ErrorCode.evidence_integrity_failed, "legacy task result has no final fact binding")
        # Preserve the completion date/historical contract. Never infer original
        # hashes from today's rows, and do not silently regenerate a report.
        self.bind_identity(conn, user)
        try:
            with deadline_scope(5.0), conn.transaction():
                conn = DeadlineConnection(conn)
                acquire_output_fence(conn)
                current = self.authenticator.authenticate(authorization, self.directory(conn))
                require_same_user(binding.user, current)
                self._validate_lookups(conn, current, binding.query_context, binding.lookups)
                facts = recheck_candidates(
                    conn,
                    [b.citation.chunk_id for b in binding.evidence],
                    as_of=binding.query_context.as_of,
                    allow_historical=binding.query_context.historical_requested,
                )
                if facts.rejected or tuple(EvidenceBinding.observed(e) for e in facts.evidence) != binding.evidence:
                    raise BusinessError(ErrorCode.evidence_integrity_failed, "stored task facts changed")
        except psycopg.Error as exc:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail=type(exc).__name__, retryable=False
            ) from None

    @staticmethod
    def _validate_lookups(
        conn: Any, user: UserContext, context: QueryContext, lookups: Sequence[LookupBinding]
    ) -> None:
        @contextmanager
        def bound(_user: UserContext) -> Iterator[Any]:
            yield conn

        evidence = evidence_lookup(bound, as_of=context.as_of, allow_historical=context.historical_requested)
        types = doc_type_lookup(bound)
        for read in lookups:
            if isinstance(read, EvidenceLookupBinding):
                fresh = tuple(EvidenceBinding.observed(e) for e in evidence(user, read.ids))
                matches = fresh == read.evidence
            else:
                matches = types(user, read.ids) == read.doc_types
            if not matches:
                raise BusinessError(ErrorCode.evidence_integrity_failed, "task lookup facts changed")

    # ---- released policy per request (M4-09: canary split, rollback without restart)
    @property
    def observation_window(self) -> timedelta:
        return timedelta(hours=float(getattr(self.settings, "observation_window_hours", 24.0)))

    @property
    def allow_drill(self) -> bool:
        return getattr(getattr(self.settings, "app_env", None), "value", None) == "dev"

    @property
    def policy_router(self) -> PolicyRouter:
        with self._composition_lock:
            if self._policy_router is None:
                self._policy_router = PolicyRouter(self.settings, self.versions.skill_version_set)
        return self._policy_router

    def route_policies(self, conn: Any, user: UserContext) -> RequestPolicies:
        return self.policy_router.route(conn, user)

    @property
    def retrieval_services(self) -> RetrievalServices:
        with self._composition_lock:
            if self._retrieval_services is None:
                self._retrieval_services = RetrievalServices(
                    self.settings, self.embedding, self.reranker, pinned=self._pinned
                )
        return self._retrieval_services

    def build_deps(
        self,
        conn: Any,
        user: UserContext,
        request: AskRequest,
        routed: RequestPolicies | None = None,
        *,
        query_context: QueryContext | None = None,
    ) -> HarnessDeps:
        selected = resolve_query_context(
            request.historical.model_dump() if request.historical else None, default_as_of=self.as_of
        )
        if query_context is not None:
            if query_context.selector != selected.selector:
                from medops.core.errors import BusinessError

                raise BusinessError(ErrorCode.invalid_request, "request and execution historical selectors disagree")
            selected = query_context
        as_of = selected.as_of
        routed = routed or self.route_policies(conn, user)
        from medops.infrastructure.db.deadline import DeadlineConnection

        conn = DeadlineConnection(conn)
        metered = MeteredGateway(self.gateway)  # Per-execution translation/generation/judgment accounting.
        retrieval = self.retrieval_services.build(conn, user, selected, routed, metered)
        reranker = self.retrieval_services.reranker_for(routed.policies.rerank_output(RERANK_OUTPUT))
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
            query_context=selected,
            execution_limits=configured_limits(self.settings),
            execution_binding=execution_binding(routed),
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
        selected = resolve_query_context(historical, default_as_of=self.as_of)
        from medops.infrastructure.db.deadline import DeadlineConnection

        conn = DeadlineConnection(conn)
        request = AskRequest(
            query="task", historical=HistoricalRequest(as_of=selected.as_of) if selected.historical_requested else None
        )
        routed = self.route_policies(conn, user)
        deps = self.build_deps(conn, user, request, routed, query_context=selected)

        @contextmanager
        def conn_for_user(_user: UserContext) -> Iterator[Any]:
            yield conn

        return SkillContext(
            user=user,
            versions=routed.versions,
            deps=deps,
            evidence_lookup=evidence_lookup(
                conn_for_user, as_of=selected.as_of, allow_historical=selected.historical_requested
            ),
            doc_type_lookup=doc_type_lookup(conn_for_user),
            trace_id=trace_id,
            run_id=trace_id,
            as_of=selected.as_of,
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

    def close(self) -> None:
        try:
            close = getattr(self.gateway, "close", None)
            if close is not None:
                close()
        finally:
            if self._pinned is not None:
                self._pinned.close()

    def ready(self) -> bool:
        if self._pinned is not None and (self._pinned.stalled or not getattr(self._pinned, "available", True)):
            return False
        status = self.retrieval_integrity()
        if not status["ready"]:
            return False
        try:
            with psycopg.connect(self._dsn, connect_timeout=2, options="-c statement_timeout=1000") as conn:
                return database_identity(conn) == status["database_identity"]
        except (psycopg.Error, ValueError):
            return False


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
