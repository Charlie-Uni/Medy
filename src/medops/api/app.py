"""FastAPI application (M3-01 first slice): `POST /v1/ask` through the fixed harness, health/readiness, and the
public error contract. Identity comes only from `medops.api.auth`; every request runs inside one database
transaction with the caller's department injected server-side (baseline 3.7) and the operation-key ledger
attached (M2-03). Responses carry the trace id in `X-Trace-Id`; errors are `ErrorResponse` without detail.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from medops.api.auth import Authenticator, PrincipalDirectory
from medops.api.contracts import AskRequest, AskResponse, EscalationReceipt, OutcomeKind, Refusal
from medops.core.errors import HTTP_STATUS, BusinessError, ErrorCode, ErrorResponse, MedOpsError
from medops.core.logging import get_logger
from medops.core.tracing import bind_trace_id
from medops.domain.common import ReasonCode
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.nodes import HarnessDeps
from medops.harness.runtime import HarnessRun, initial_state, run_ask

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

    def build_deps(self, conn: Any, user: UserContext, request: AskRequest) -> HarnessDeps: ...

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


def create_app(runtime: ApiRuntime, *, docs_enabled: bool = False, debug: bool = False) -> FastAPI:
    app = FastAPI(
        title="MedOps Copilot",
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
        debug=debug,
    )

    @app.middleware("http")
    async def trace_scope(request: Request, call_next: Callable[[Request], Any]) -> Any:
        with bind_trace_id() as trace_id:
            request.state.trace_id = trace_id
            try:
                response = await call_next(request)
            except MedOpsError as exc:
                response = _error_response(exc.code, exc.message, trace_id, retryable=exc.retryable)
            except Exception:  # noqa: BLE001 - the public contract never leaks internals (baseline 5.12)
                log.exception("unhandled error", extra={"path": request.url.path})
                response = _error_response(
                    ErrorCode.internal_error, "服务暂时不可用，请稍后重试", trace_id, retryable=False
                )
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
            deps = runtime.build_deps(conn, user, body)
            state = initial_state(
                user=user,
                query=body.query,
                versions=runtime.versions,
                trace_id=trace_id,
                historical_requested=body.historical is not None,
            )
            run = run_ask(state, deps)
        return to_ask_response(run, trace_id, runtime.versions)

    return app


@dataclass(frozen=True)
class NoDatabase:
    """Connection provider for runtimes without a fact plane (unit tests)."""

    @contextmanager
    def __call__(self) -> Iterator[None]:
        yield None
