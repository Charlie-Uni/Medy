"""Run one ask through the compiled graph and return the final state with every node attempt."""

from __future__ import annotations

from dataclasses import dataclass

from medops.core.telemetry import annotate, run_metadata, span
from medops.core.tracing import new_trace_id
from medops.domain.identity import UserContext
from medops.domain.intent import Entity
from medops.domain.state import AgentState, TokenBudget, VersionSet
from medops.harness.contracts import NodeAttempt
from medops.harness.dependencies import HarnessDeps
from medops.harness.graph import build_graph

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
        historical_requested=historical_requested,
    )


def run_ask(state: AgentState, deps: HarnessDeps, *, recursion_limit: int = 12) -> HarnessRun:
    with (
        run_metadata(state.trace_id, state.versions.model_dump(mode="json"), kind="ask"),
        span("harness.run") as current,
    ):
        app = build_graph(deps)
        result = app.invoke(
            {"state": state, "attempts": [], "flagged": []}, config={"recursion_limit": recursion_limit}
        )
        final: AgentState = result["state"]
        if final.answer is None and final.escalation is None:
            raise AssertionError("harness ended without an answer or an escalation")
        annotate(current, outcome="answered" if final.answer is not None else "escalated")
        return HarnessRun(state=final, attempts=tuple(result["attempts"]), flagged_evidence=tuple(result["flagged"]))
