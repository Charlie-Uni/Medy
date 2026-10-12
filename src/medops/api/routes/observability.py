"""Operational metrics, trace replay and restricted payload access."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from medops.api.authorization import privileged_connection
from medops.api.ports import ApiRuntime
from medops.application.contracts import (
    AskRequest,
    ReplayReport,
    ReplayRequest,
    TracePayloadResponse,
)
from medops.application.metrics import has_role, render_prometheus
from medops.application.replay import ReplayService
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.domain.state import VersionSet
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
            runtime.validate_privileged_access(conn, conn, user, authorization=request.headers.get("authorization"))
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

            def deps_for(
                user: UserContext, context: QueryContext, original: AskRequest
            ) -> tuple[HarnessDeps, VersionSet]:
                runtime.bind_identity(conn, user)  # the replay runs under the original principal, not the admin
                routed = runtime.route_policies(conn, user)
                deps = runtime.build_deps(
                    conn,
                    user,
                    original,
                    routed,
                    query_context=context,
                )
                return deps, routed.versions

            def load_payload(user: UserContext, tid: str, purpose: str) -> TracePayloadResponse:
                from medops.infrastructure.db.final_output import require_same_user

                # Release this separate identity fence before hosted replay work.
                with privileged_connection(runtime, request, "admin", kind="restricted") as (current, rconn):
                    require_same_user(user, current)
                    return runtime.payload_reader(rconn).read(current, tid, purpose)

            writer = runtime.payload_writer(conn)

            service = ReplayService(
                store=runtime.trace_store(conn),
                build_deps=deps_for,
                resolve_user=lambda principal: runtime.resolve_user(conn, principal),
                payload_writer=writer,
                load_payload=load_payload if writer is not None else None,
            )
            report = service.replay(admin, trace_id, body)
            runtime.validate_privileged_access(conn, conn, admin, authorization=request.headers.get("authorization"))
            return report

    @router.get("/admin/traces/{trace_id}/payload", response_model=TracePayloadResponse)
    def read_trace_payload(trace_id: str, purpose: str, request: Request) -> TracePayloadResponse:
        """Restricted replay payload (DEC-013): admin role, stated purpose, every read logged before plaintext leaves."""
        if not 8 <= len(purpose) <= 500:
            raise BusinessError(ErrorCode.invalid_request, "purpose must be 8-500 characters")
        with privileged_connection(runtime, request, "admin", kind="restricted") as (admin, rconn):
            return runtime.payload_reader(rconn).read(admin, trace_id, purpose)

    return router
