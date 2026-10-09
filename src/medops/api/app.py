"""FastAPI application (M3-01 first slice): `POST /v1/ask` through the fixed harness, health/readiness, and the
public error contract. Identity comes only from `medops.api.auth`; every request runs inside one database
transaction with the caller's department injected server-side (baseline 3.7) and the operation-key ledger
attached (M2-03). Responses carry the trace id in `X-Trace-Id`; errors are `ErrorResponse` without detail.
"""

from __future__ import annotations

import traceback
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from medops.api.ports import ApiRuntime
from medops.api.responses import TRACE_HEADER, _error_response
from medops.api.routes import admin, ask, observability, tasks
from medops.core.errors import ErrorCode, MedOpsError
from medops.core.logging import get_logger
from medops.core.telemetry import ATTR_POLICY, ATTR_RETRIEVAL, annotate, span
from medops.core.telemetry import flush as flush_telemetry
from medops.core.tracing import bind_trace_id

log = get_logger(__name__)


def error_frames(exc: BaseException, limit: int = 12) -> list[str]:
    """Where an unhandled error happened, without any value: `file:line function` of the innermost frames. The
    exception message stays out of the log on purpose (it can quote the request; record 141), the frames do not."""
    return [
        f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno} {frame.name}"
        for frame in traceback.extract_tb(exc.__traceback__)[-limit:]
    ]


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
                "http.route": "/<unmatched>",
                ATTR_POLICY: runtime.versions.policy_version,
                ATTR_RETRIEVAL: runtime.versions.retrieval_version,
            }
            with span("http.request", **attrs) as current:
                try:
                    response = await call_next(request)
                except MedOpsError as exc:
                    response = _error_response(exc.code, exc.message, trace_id, retryable=exc.retryable)
                except Exception as exc:  # noqa: BLE001 - the public contract never leaks internals (baseline 5.12)
                    log.error(
                        "unhandled error",
                        extra={"fields": {"error_type": type(exc).__name__, "frames": error_frames(exc)}},
                    )
                    response = _error_response(
                        ErrorCode.internal_error, "服务暂时不可用，请稍后重试", trace_id, retryable=False
                    )
                route = getattr(request.scope.get("route"), "path", "/<unmatched>")
                annotate(current, **{"http.status_code": response.status_code, "http.route": route})
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
    def readyz() -> JSONResponse:
        ok = runtime.ready()
        return JSONResponse(status_code=200 if ok else 503, content={"status": "ok" if ok else "not_ready"})

    app.include_router(ask.build_router(runtime))
    app.include_router(tasks.build_router(runtime, idempotency_ttl_s=idempotency_ttl_s))
    app.include_router(observability.build_router(runtime))
    app.include_router(admin.build_router(runtime, idempotency_ttl_s=idempotency_ttl_s))
    return app
