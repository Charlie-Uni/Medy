"""Grounded question answering and its transactional audit trail."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from medops.api.contracts import (
    AskRequest,
    AskResponse,
)
from medops.api.ports import ApiRuntime
from medops.api.responses import to_ask_response
from medops.application.audit import record_or_fail_closed, trace_from_run
from medops.core.errors import BusinessError, ErrorCode
from medops.harness.runtime import initial_state, run_ask
from medops.infrastructure.llm.meter import MeteredGateway


def build_router(runtime: ApiRuntime) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/ask", response_model=AskResponse, response_model_exclude_none=False)
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

    return router
