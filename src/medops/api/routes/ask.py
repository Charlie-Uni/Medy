"""Grounded question answering and its transactional audit trail."""

from __future__ import annotations

import time
from dataclasses import replace

from fastapi import APIRouter, Request

from medops.api.ports import ApiRuntime
from medops.api.responses import to_ask_response
from medops.application.audit import trace_from_run
from medops.application.contracts import (
    AskRequest,
    AskResponse,
)
from medops.application.execution_audit import ExecutionAuditWriter
from medops.application.payloads import payloads_from_run
from medops.core.deadline import deadline_scope
from medops.core.errors import ErrorCode, MedOpsError
from medops.domain.common import ReasonCode
from medops.domain.query import resolve_query_context
from medops.harness.audit import ExecutionAudit
from medops.harness.runtime import initial_state, run_ask
from medops.harness.transitions import escalate
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.llm.meter import MeteredGateway


def build_router(runtime: ApiRuntime) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/ask", response_model=AskResponse, response_model_exclude_none=False)
    def ask(body: AskRequest, request: Request) -> AskResponse:
        trace_id: str = request.state.trace_id
        resolve_query_context(body.historical.model_dump() if body.historical else None)
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
            runtime.bind_identity(conn, user)
            routed = runtime.route_policies(conn, user)  # M4-09: released pointers + canary split, per request
            deps = replace(runtime.build_deps(conn, user, body, routed), audit=ExecutionAudit())
            state = initial_state(
                user=user,
                query=body.query,
                versions=routed.versions,
                trace_id=trace_id,
                historical_requested=body.historical is not None,
                query_context=deps.query_context
                or resolve_query_context(
                    body.historical.model_dump() if body.historical else None, default_as_of=deps.as_of
                ),
            )
            started = time.perf_counter()
            total_s = (
                deps.execution_limits.timeout_s
                if deps.execution_limits
                else sum(spec.timeout_s for spec in deps.specs.values())
            )
            guarded_conn = DeadlineConnection(conn)
            with deadline_scope(total_s):
                run = run_ask(state, deps)
                with deadline_scope(5.0):
                    assert run.state.query_context is not None and deps.audit is not None
                    # Protect the complete evidence set and identity until this transaction's
                    # audit commits. Inference is finished; no extra model call or repair.
                    try:
                        runtime.validate_final_output(
                            guarded_conn,
                            user,
                            run.state.evidence,
                            run.state.query_context,
                            authorization=request.headers.get("authorization"),
                        )
                    except MedOpsError as exc:
                        code = (
                            ReasonCode.acl_denied
                            if exc.code in (ErrorCode.forbidden, ErrorCode.unauthenticated)
                            else ReasonCode.system_failure
                        )
                        deps.audit.record_event("final_output", {"status": "withheld", "error_code": exc.code.value})
                        run = replace(run, state=escalate(run.state, (code,), "final output check failed", answer=None))
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
                    ExecutionAuditWriter(
                        runtime.trace_store(guarded_conn), runtime.payload_writer(guarded_conn)
                    ).record(
                        trace,
                        escalation,
                        node="ask",
                        payloads=payloads_from_run(
                            run, query=body.query, request=body.model_dump(mode="json"), audit=deps.audit
                        ),
                    )
        return response

    return router
