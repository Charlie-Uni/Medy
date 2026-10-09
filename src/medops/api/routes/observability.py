"""Operational metrics, trace replay and restricted payload access."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from medops.api.contracts import (
    AskRequest,
    ReplayReport,
    ReplayRequest,
    TracePayloadResponse,
)
from medops.api.ports import ApiRuntime
from medops.application.metrics import has_role, render_prometheus
from medops.application.replay import ReplayService
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext
from medops.harness.dependencies import HarnessDeps


def build_router(runtime: ApiRuntime) -> APIRouter:
    router = APIRouter()

    @router.get("/metrics")
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

    @router.post("/admin/traces/{trace_id}/replay", response_model=ReplayReport, status_code=201)
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

    @router.get("/admin/traces/{trace_id}/payload", response_model=TracePayloadResponse)
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

    return router
