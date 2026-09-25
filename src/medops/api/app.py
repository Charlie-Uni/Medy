"""FastAPI application (M3-01 first slice): `POST /v1/ask` through the fixed harness, health/readiness, and the
public error contract. Identity comes only from `medops.api.auth`; every request runs inside one database
transaction with the caller's department injected server-side (baseline 3.7) and the operation-key ledger
attached (M2-03). Responses carry the trace id in `X-Trace-Id`; errors are `ErrorResponse` without detail.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable, Iterator, Mapping
from contextlib import AbstractContextManager, asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from medops.api.auth import Authenticator, PrincipalDirectory
from medops.api.contracts import (
    IDEMPOTENCY_KEY_HEADER,
    AskRequest,
    AskResponse,
    DocumentAclRequest,
    DocumentAclResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentStatusRequest,
    EscalationReceipt,
    FeedbackReceipt,
    FeedbackRequest,
    OutcomeKind,
    PolicyDecisionRequest,
    PolicyListResponse,
    PolicyPromoteRequest,
    PolicyReleaseRequest,
    PolicyResponse,
    PolicyRollbackRequest,
    Refusal,
    ReplayReport,
    ReplayRequest,
    TaskCreateRequest,
    TaskResponse,
    TracePayloadResponse,
)
from medops.application.admin import (
    DocumentActions,
    DocumentAdminService,
    DocumentAdminStore,
    PolicyService,
    PolicyStore,
    ReceiptStore,
    idempotent,
)
from medops.application.audit import FeedbackService, TraceStore, record_or_fail_closed, trace_from_run
from medops.application.metrics import MetricsSource, has_role, render_prometheus
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.policy_loader import RequestPolicies
from medops.application.replay import ReplayService
from medops.application.tasks import TaskService, TaskStore, to_response
from medops.core.errors import HTTP_STATUS, BusinessError, ErrorCode, ErrorResponse, MedOpsError
from medops.core.logging import get_logger
from medops.core.telemetry import ATTR_POLICY, ATTR_RETRIEVAL, annotate, span
from medops.core.telemetry import flush as flush_telemetry
from medops.core.tracing import bind_trace_id
from medops.domain.common import ReasonCode
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.nodes import HarnessDeps
from medops.harness.runtime import HarnessRun, initial_state, run_ask
from medops.infrastructure.llm.meter import MeteredGateway

log = get_logger(__name__)
TRACE_HEADER = "X-Trace-Id"
# Refusals (baseline 5.5): the request itself is not answerable by policy. Everything else is an escalation
# the caller can wait on. High-risk questions are refused *and* recorded as an escalation inside the run.
REFUSAL_CODES: frozenset[ReasonCode] = frozenset(
    {ReasonCode.high_risk_medical, ReasonCode.prompt_injection, ReasonCode.acl_denied}
)
PUBLIC_MESSAGES: Mapping[ReasonCode, str] = {
    ReasonCode.high_risk_medical: "该问题涉及诊断、处方或个体用药调整，系统不提供此类回答；已转人工处理",
    ReasonCode.prompt_injection: "请求包含试图改变系统行为的内容，已拒绝",
    ReasonCode.acl_denied: "当前身份无权访问所需文档",
    ReasonCode.insufficient_evidence: "现有文档证据不足以回答该问题，已记录待人工补充",
    ReasonCode.version_conflict: "相关文档存在版本冲突，已升级人工核对",
    ReasonCode.unsupported_conclusion: "生成内容未能通过证据核验，已升级人工处理",
    ReasonCode.budget_exceeded: "本次请求超出处理预算，已升级人工处理",
    ReasonCode.intent_unclear: "问题不够明确，请补充具体药品、文件或场景后重试",
    ReasonCode.system_failure: "系统处理失败，已记录；请稍后重试或等待人工处理",
}


class ApiRuntime(Protocol):
    """What the routes need from the environment; production wires PostgreSQL, the retrieval stack and the
    gateway, tests wire fakes. `connection()` must yield a connection inside a transaction that is committed
    on normal exit and rolled back on error."""

    authenticator: Authenticator
    versions: VersionSet

    def connection(self) -> AbstractContextManager[Any]: ...

    def directory(self, conn: Any) -> PrincipalDirectory: ...

    def bind_identity(self, conn: Any, user: UserContext) -> None: ...

    def route_policies(self, conn: Any, user: UserContext) -> RequestPolicies: ...

    def build_deps(
        self, conn: Any, user: UserContext, request: AskRequest, routed: RequestPolicies | None = None
    ) -> HarnessDeps: ...

    def task_store(self, conn: Any) -> TaskStore: ...

    def trace_store(self, conn: Any) -> TraceStore: ...

    def metrics_source(self, conn: Any) -> MetricsSource: ...

    def resolve_user(self, conn: Any, principal: str) -> UserContext | None: ...

    # M3-03 admin routes run on the admin database role (INV-AUTH-05: separated roles); the unit-test runtime yields None
    def admin_connection(self) -> AbstractContextManager[Any]: ...

    def document_admin(self, conn: Any) -> tuple[DocumentAdminStore, DocumentActions]: ...

    def policy_store(self, conn: Any) -> PolicyStore: ...

    def receipt_store(self, conn: Any) -> ReceiptStore | None: ...

    # M3-07 restricted payloads (DEC-013): writer on the request connection (None = disabled), reader on the restricted role
    def payload_writer(self, conn: Any) -> PayloadWriter | None: ...

    def restricted_connection(self) -> AbstractContextManager[Any]: ...

    def payload_reader(self, conn: Any) -> PayloadReader: ...

    @property
    def monthly_cap_usd(self) -> float | None: ...

    def ready(self) -> bool: ...


def _error_response(code: ErrorCode, message: str, trace_id: str | None, *, retryable: bool) -> JSONResponse:
    body = ErrorResponse(code=code, message=message, trace_id=trace_id, retryable=retryable)
    return JSONResponse(
        status_code=HTTP_STATUS[code], content=body.model_dump(mode="json"), headers={TRACE_HEADER: trace_id or ""}
    )


def to_ask_response(run: HarnessRun, trace_id: str, versions: VersionSet) -> AskResponse:
    if run.state.answer is not None:
        return AskResponse(trace_id=trace_id, outcome=OutcomeKind.answered, versions=versions, answer=run.state.answer)
    esc = run.state.escalation
    assert esc is not None  # run_ask guarantees an answer or an escalation
    codes = esc.reason_codes
    message = "；".join(dict.fromkeys(PUBLIC_MESSAGES.get(c, c.value) for c in codes))
    if set(codes) <= REFUSAL_CODES:
        return AskResponse(
            trace_id=trace_id,
            outcome=OutcomeKind.refused,
            versions=versions,
            refusal=Refusal(reason_codes=codes, message=message),
        )
    return AskResponse(
        trace_id=trace_id,
        outcome=OutcomeKind.escalated,
        versions=versions,
        escalation=EscalationReceipt(escalation_id=trace_id, reason_codes=codes, message=message),
    )


def create_app(
    runtime: ApiRuntime, *, docs_enabled: bool = False, debug: bool = False, idempotency_ttl_s: int = 7 * 24 * 3600
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        flush_telemetry()  # graceful stop: the last spans leave before uvicorn re-raises the signal (record 77)

    app = FastAPI(
        title="MedOps Copilot",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
        debug=debug,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def trace_scope(request: Request, call_next: Callable[[Request], Any]) -> Any:
        with bind_trace_id() as trace_id:
            request.state.trace_id = trace_id
            attrs = {
                "http.method": request.method,
                "http.route": request.url.path,
                ATTR_POLICY: runtime.versions.policy_version,
                ATTR_RETRIEVAL: runtime.versions.retrieval_version,
            }
            with span("http.request", **attrs) as current:
                try:
                    response = await call_next(request)
                except MedOpsError as exc:
                    response = _error_response(exc.code, exc.message, trace_id, retryable=exc.retryable)
                except Exception:  # noqa: BLE001 - the public contract never leaks internals (baseline 5.12)
                    log.exception("unhandled error", extra={"path": request.url.path})
                    response = _error_response(
                        ErrorCode.internal_error, "服务暂时不可用，请稍后重试", trace_id, retryable=False
                    )
                annotate(current, **{"http.status_code": response.status_code})
            response.headers[TRACE_HEADER] = trace_id
            return response

    @app.exception_handler(MedOpsError)
    async def medops_error(request: Request, exc: MedOpsError) -> JSONResponse:
        return _error_response(exc.code, exc.message, getattr(request.state, "trace_id", None), retryable=exc.retryable)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_response(
            ErrorCode.schema_violation,
            "request rejected by the API schema",
            getattr(request.state, "trace_id", None),
            retryable=False,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> JSONResponse:
        ok = runtime.ready()
        return JSONResponse(status_code=200 if ok else 503, content={"status": "ok" if ok else "not_ready"})

    @app.post("/v1/ask", response_model=AskResponse, response_model_exclude_none=False)
    def ask(body: AskRequest, request: Request) -> AskResponse:
        trace_id: str = request.state.trace_id
        if body.historical is not None and body.historical.version is not None:
            raise BusinessError(
                ErrorCode.invalid_request, "historical version selector arrives with the task API (M3-03); use as_of"
            )
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            runtime.bind_identity(conn, user)
            routed = runtime.route_policies(conn, user)  # M4-09: released pointers + canary split, per request
            deps = runtime.build_deps(conn, user, body, routed)
            state = initial_state(
                user=user,
                query=body.query,
                versions=routed.versions,
                trace_id=trace_id,
                historical_requested=body.historical is not None,
            )
            started = time.perf_counter()
            run = run_ask(state, deps)
            response = to_ask_response(run, trace_id, routed.versions)
            meter = deps.gateway if isinstance(deps.gateway, MeteredGateway) else None
            trace, escalation = trace_from_run(
                run,
                kind="ask",
                user=user,
                query=body.query,
                versions=routed.versions,
                outcome=response.outcome.value,
                model_calls=meter.calls if meter else 0,
                tokens=meter.tokens if meter else run.state.budget.used,
                cost_usd=meter.cost_usd if meter else 0.0,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            # the audit write is part of the request transaction: no trace, no answer (baseline 5.10)
            record_or_fail_closed(runtime.trace_store(conn), trace, escalation)
            writer = runtime.payload_writer(conn)
            if writer is not None:  # same transaction: the replay payload exists iff the trace exists
                writer.record_run(run, query=body.query)
        return response

    def _tasks(conn: Any) -> TaskService:
        return TaskService(store=runtime.task_store(conn), idempotency_ttl_s=idempotency_ttl_s)

    @app.get("/metrics")
    def metrics(request: Request) -> PlainTextResponse:
        """Operational metrics (M3-10): aggregate, low-cardinality; readable by principals with the ops or admin role."""
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            if not has_role(user.roles, "ops", "admin"):
                raise BusinessError(ErrorCode.forbidden, "metrics require the ops or admin role")
            snapshot = runtime.metrics_source(conn).snapshot(window_minutes=60, now=datetime.now(UTC))
        return PlainTextResponse(
            render_prometheus(snapshot, monthly_cap_usd=runtime.monthly_cap_usd), media_type="text/plain; version=0.0.4"
        )

    @app.post("/admin/traces/{trace_id}/replay", response_model=ReplayReport, status_code=201)
    def replay_trace(trace_id: str, body: ReplayRequest, request: Request) -> ReplayReport:
        with runtime.connection() as conn:
            admin = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            if not has_role(admin.roles, "admin"):
                raise BusinessError(ErrorCode.forbidden, "replay requires the admin role")

            def deps_for(user: UserContext) -> HarnessDeps:
                runtime.bind_identity(conn, user)  # the replay runs under the original principal, not the admin
                return runtime.build_deps(conn, user, AskRequest(query="replay"), runtime.route_policies(conn, user))

            service = ReplayService(
                store=runtime.trace_store(conn),
                versions=runtime.versions,
                versions_for=lambda user: runtime.route_policies(conn, user).versions,
                build_deps=deps_for,
                resolve_user=lambda principal: runtime.resolve_user(conn, principal),
                payload_writer=runtime.payload_writer(conn),
            )
            return service.replay(admin, trace_id, body)

    @app.post("/v1/tasks", response_model=TaskResponse, status_code=202)
    def create_task(body: TaskCreateRequest, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).create(user, body, request.headers.get(IDEMPOTENCY_KEY_HEADER))
        return to_response(record)

    @app.get("/v1/tasks/{task_id}", response_model=TaskResponse)
    def get_task(task_id: str, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).get(user, task_id)
        return to_response(record)

    @app.post("/v1/feedback", response_model=FeedbackReceipt, status_code=201)
    def feedback(body: FeedbackRequest, request: Request) -> FeedbackReceipt:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            service = FeedbackService(store=runtime.trace_store(conn), idempotency_ttl_s=idempotency_ttl_s)
            return service.submit(user, body, request.headers.get(IDEMPOTENCY_KEY_HEADER))

    @app.post("/v1/tasks/{task_id}/retry", response_model=TaskResponse, status_code=202)
    def retry_task(task_id: str, request: Request) -> TaskResponse:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            record = _tasks(conn).retry(user, task_id)
        return to_response(record)

    @app.get("/admin/traces/{trace_id}/payload", response_model=TracePayloadResponse)
    def read_trace_payload(trace_id: str, purpose: str, request: Request) -> TracePayloadResponse:
        """Restricted replay payload (DEC-013): admin role, stated purpose, every read logged before plaintext leaves."""
        if not 8 <= len(purpose) <= 500:
            raise BusinessError(ErrorCode.invalid_request, "purpose must be 8-500 characters")
        with runtime.connection() as conn:
            admin = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
        if not has_role(admin.roles, "admin"):
            raise BusinessError(ErrorCode.forbidden, "restricted payloads require the admin role")
        with runtime.restricted_connection() as rconn:
            return runtime.payload_reader(rconn).read(admin, trace_id, purpose)

    # ------------------------------------------------------------------ admin: documents and policies (M3-03, DEC-012)

    def _admin_user(request: Request, *roles: str) -> UserContext:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
        if not has_role(user.roles, *roles):
            raise BusinessError(ErrorCode.forbidden, f"requires one of the roles: {', '.join(roles)}")
        return user

    def _documents(conn: Any) -> DocumentAdminService:
        store, actions = runtime.document_admin(conn)
        return DocumentAdminService(store=store, actions=actions)

    @app.get("/admin/documents", response_model=DocumentListResponse)
    def list_documents(
        request: Request, dept: str | None = None, status: str | None = None, family_id: str | None = None
    ) -> DocumentListResponse:
        _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            return _documents(conn).list(dept=dept, status=status, family_id=family_id)

    @app.get("/admin/documents/{doc_id}", response_model=DocumentDetail)
    def get_document(doc_id: str, request: Request) -> DocumentDetail:
        _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            return _documents(conn).get(doc_id)

    @app.patch("/admin/documents/{doc_id}/status", response_model=DocumentDetail)
    def change_document_status(doc_id: str, body: DocumentStatusRequest, request: Request) -> DocumentDetail:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _documents(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"PATCH /admin/documents/{doc_id}/status",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                DocumentDetail,
                lambda: service.change_status(admin, doc_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @app.patch("/admin/documents/{doc_id}/acl", response_model=DocumentAclResponse)
    def change_document_acl(doc_id: str, body: DocumentAclRequest, request: Request) -> DocumentAclResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _documents(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"PATCH /admin/documents/{doc_id}/acl",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                DocumentAclResponse,
                lambda: service.change_acl(admin, doc_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @app.get("/admin/policies/candidates", response_model=PolicyListResponse)
    def list_policy_candidates(request: Request) -> PolicyListResponse:
        _admin_user(request, "approver", "admin")
        with runtime.admin_connection() as conn:
            return _policy_service(conn).list_candidates()

    @app.get("/admin/policies/{policy_id}", response_model=PolicyResponse)
    def get_policy(policy_id: str, request: Request) -> PolicyResponse:
        _admin_user(request, "approver", "admin")
        with runtime.admin_connection() as conn:
            return _policy_service(conn).get(policy_id)

    @app.post("/admin/policies/{policy_id}/approve", response_model=PolicyResponse)
    def decide_policy(policy_id: str, body: PolicyDecisionRequest, request: Request) -> PolicyResponse:
        approver = _admin_user(request, "approver")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                approver,
                f"POST /admin/policies/{policy_id}/approve",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.decide(approver, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    def _policy_service(conn: Any) -> PolicyService:
        return PolicyService(
            store=runtime.policy_store(conn),
            observation_window=getattr(runtime, "observation_window", timedelta(hours=24)),
            allow_drill=bool(getattr(runtime, "allow_drill", False)),
        )

    @app.post("/admin/policies/{policy_id}/release", response_model=PolicyResponse)
    def release_policy(policy_id: str, body: PolicyReleaseRequest, request: Request) -> PolicyResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"POST /admin/policies/{policy_id}/release",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.release(admin, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @app.post("/admin/policies/{policy_id}/promote", response_model=PolicyResponse)
    def promote_policy(policy_id: str, body: PolicyPromoteRequest, request: Request) -> PolicyResponse:
        approver = _admin_user(request, "approver")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                approver,
                f"POST /admin/policies/{policy_id}/promote",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.promote(approver, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @app.post("/admin/policies/{policy_id}/rollback", response_model=PolicyResponse)
    def rollback_policy(policy_id: str, body: PolicyRollbackRequest, request: Request) -> PolicyResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"POST /admin/policies/{policy_id}/rollback",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.rollback(admin, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    return app


@dataclass(frozen=True)
class NoDatabase:
    """Connection provider for runtimes without a fact plane (unit tests)."""

    @contextmanager
    def __call__(self) -> Iterator[None]:
        yield None
