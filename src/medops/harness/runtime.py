"""Run one ask through the compiled graph and return the final state with every node attempt."""

from __future__ import annotations

from dataclasses import dataclass, replace

from medops.core.errors import BusinessError, ErrorCode
from medops.core.telemetry import annotate, run_metadata, span
from medops.core.tracing import new_trace_id
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.query import QueryContext, resolve_query_context
from medops.domain.state import AgentState, TokenBudget, VersionSet
from medops.harness.contracts import NodeAttempt
from medops.harness.dependencies import HarnessDeps
from medops.harness.graph import build_graph
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.execution_budget import EXECUTION_BUDGET_VERSION, default_limits, execution_scope
from medops.infrastructure.llm.meter import MeteredGateway

DEFAULT_TRACE_TOKEN_LIMIT = 12_000  # INV-HAR-08: whole-trace budget, not a per-call max_tokens


@dataclass(frozen=True)
class HarnessRun:
    state: AgentState
    attempts: tuple[NodeAttempt, ...]
    flagged_evidence: tuple[str, ...]

    @property
    def outcome(self) -> str:
        if self.state.answer is not None:
            return "answered"
        return "escalated"


def initial_state(
    *,
    user: UserContext,
    query: str,
    versions: VersionSet,
    trace_id: str | None = None,
    run_id: str | None = None,
    token_limit: int = DEFAULT_TRACE_TOKEN_LIMIT,
    session_entities: tuple[Entity, ...] = (),
    historical_requested: bool = False,
    query_context: QueryContext | None = None,
) -> AgentState:
    trace = trace_id or new_trace_id()
    return AgentState(
        trace_id=trace,
        run_id=run_id or trace,  # production: run_id == trace_id; replays pass a separate replay_run_id
        user=user,
        query=query,
        versions=versions,
        budget=TokenBudget(limit=token_limit, used=0),
        session_entities=session_entities,
        historical_requested=query_context.historical_requested if query_context is not None else historical_requested,
        query_context=query_context,
    )


def run_ask(state: AgentState, deps: HarnessDeps, *, recursion_limit: int = 12) -> HarnessRun:
    context = state.query_context or deps.query_context
    if context is None:
        if state.historical_requested:
            if deps.as_of is None:
                raise BusinessError(ErrorCode.invalid_request, "historical execution requires an explicit date")
            context = QueryContext(as_of=deps.as_of, historical_requested=True)
        else:
            context = resolve_query_context(None, default_as_of=deps.as_of)
    if (
        context.historical_requested != state.historical_requested
        or (deps.as_of is not None and context.as_of != deps.as_of)
        or (deps.query_context is not None and context != deps.query_context)
    ):
        raise BusinessError(ErrorCode.invalid_request, "execution historical context disagrees")
    state = state.advance(query_context=context)
    deps = replace(deps, as_of=context.as_of, query_context=context)
    limits = deps.execution_limits or default_limits(
        timeout_s=sum(s.timeout_s for s in deps.specs.values()), token_limit=state.budget.limit
    )
    limits = limits.model_copy(update={"token_limit": min(limits.token_limit, state.budget.limit)})
    if not isinstance(deps.gateway, MeteredGateway):
        deps = replace(deps, gateway=MeteredGateway(deps.gateway))
    with (
        run_metadata(state.trace_id, state.versions.model_dump(mode="json"), kind="ask"),
        call_scope(run_id=state.run_id),
        execution_scope(limits) as budget,
        span("harness.run") as current,
    ):
        app = build_graph(deps)
        result = app.invoke(
            {"state": state, "attempts": [], "flagged": []}, config={"recursion_limit": recursion_limit}
        )
        final: AgentState = result["state"]
        snapshot = budget.snapshot()
        if snapshot.accounted_tokens and snapshot.accounted_tokens <= state.budget.limit:
            final = final.advance(budget=TokenBudget(limit=state.budget.limit, used=snapshot.accounted_tokens))
        annotate(
            current,
            execution_budget_version=EXECUTION_BUDGET_VERSION,
            execution_timeout_s=snapshot.limits.timeout_s,
            execution_token_limit=snapshot.limits.token_limit,
            execution_cost_limit_usd=snapshot.limits.cost_limit_usd,
            execution_accounted_tokens=snapshot.accounted_tokens,
            execution_accounted_cost_usd=snapshot.accounted_cost_usd,
            execution_reserved_tokens=snapshot.reserved_tokens,
            execution_budget_blocked=snapshot.blocked_reason,
        )
        if final.answer is None and final.escalation is None:
            raise AssertionError("harness ended without an answer or an escalation")
        annotate(current, outcome="answered" if final.answer is not None else "escalated")
        return HarnessRun(state=final, attempts=tuple(result["attempts"]), flagged_evidence=tuple(result["flagged"]))
