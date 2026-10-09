"""Harness nodes (baseline 5.3). Each node: builds its operation key, runs its body under the node policy
(`run_node`), advances `AgentState`, and on final failure records an escalation instead of guessing.

Safety layers by data flow: layer 1 (user input) inside Intent, layer 2 (retrieved content) inside Retrieve,
the Safety node decision before Answer, layer 3 (rendered output) inside Answer. Answer only ever receives
`state.evidence` (INV-HAR-03) and its result is re-verified before it becomes `state.answer`.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from medops.core.canonical import operation_key
from medops.domain.common import ReasonCode
from medops.domain.evidence import Evidence
from medops.domain.intent import IntentType
from medops.domain.safety import SafetyDecision, SafetyResult
from medops.domain.state import MAX_CANDIDATES, AgentState, TokenBudget
from medops.harness.answer import answer_model, generate_answer
from medops.harness.contracts import NodeAttempt, NodeFailure, run_node
from medops.harness.dependencies import HarnessDeps
from medops.harness.executions import apply_delta, state_delta
from medops.harness.intent import INTENT_VERSION, classify
from medops.harness.retrieval_port import RetrievalRequest
from medops.harness.transitions import escalate as _escalate
from medops.infrastructure.llm.gateway import (
    BudgetExceeded,
    ModelOutputInvalid,
    estimate_tokens,
)
from medops.safety.checks import SAFETY_VERSION, check_input, decide, screen_evidence
from medops.verification.verifier import verify_evidence

NODE_ORDER = ("intent", "retrieve", "verify", "safety", "answer", "escalate")
OPERATION_SCOPE = "harness"
ANSWER_PROMPT_RESERVE = 1500  # prompt scaffolding + verifier calls, on top of the answer allowance


class HarnessState(TypedDict):
    state: AgentState
    attempts: Annotated[list[NodeAttempt], operator.add]
    flagged: Annotated[list[str], operator.add]  # evidence chunk ids excluded by safety layer 2


def _failure_codes(exc: BaseException) -> tuple[ReasonCode, str]:
    if isinstance(exc, BudgetExceeded):
        return ReasonCode.budget_exceeded, str(exc)[:200]
    if isinstance(exc, ModelOutputInvalid):
        return ReasonCode.system_failure, f"model output invalid: {exc}"[:200]
    return ReasonCode.system_failure, f"{type(exc).__name__}"[:200]


def _key(state: AgentState, node: str, **inputs: Any) -> str:
    payload = {
        "query": state.query,
        "dept": state.user.dept.value,
        "historical_requested": state.historical_requested,
        "versions": state.versions.model_dump(),
        **inputs,
    }
    return operation_key(OPERATION_SCOPE, state.run_id, node, payload)


def build_nodes(deps: HarnessDeps) -> dict[str, Callable[[HarnessState], dict[str, Any]]]:
    specs = deps.specs

    def guarded(
        node: str, hs: HarnessState, key: str, body: Callable[[AgentState], AgentState | tuple[AgentState, list[str]]]
    ) -> dict[str, Any]:
        state = hs["state"]
        store = deps.executions
        claim_no = 0
        if store is not None:
            claim = store.claim(
                operation_key=key,
                operation_scope=OPERATION_SCOPE,
                run_id=state.run_id,
                trace_id=state.trace_id,
                node_name=node,
                versions=state.versions.model_dump(mode="json"),
                now=deps.clock(),
            )
            if claim.kind == "reused" and claim.result is not None:
                # same operation key, succeeded before: the stored delta is re-applied, no side effect repeats
                reused = apply_delta(state, claim.result["state_delta"])
                return {"state": reused, "attempts": [], "flagged": list(claim.result.get("flagged", []))}
            if claim.kind == "in_flight":
                return {
                    "state": _escalate(state, (ReasonCode.system_failure,), f"{node}: operation already in flight"),
                    "attempts": [],
                }
            claim_no = claim.claim_no
        try:
            result, attempts = run_node(specs[node], key, lambda: body(state), sleep=deps.sleep, clock=deps.clock)
        except NodeFailure as failure:
            code, detail = _failure_codes(failure.error)
            if store is not None:
                store.record_attempts(claim_no, failure.attempts)
                store.fail(key, failure.attempts[-1].error_code or code.value, deps.clock())
            return {"state": _escalate(state, (code,), f"{node}: {detail}"), "attempts": failure.attempts}
        if isinstance(result, tuple):
            new_state, flagged = result
        else:
            new_state, flagged = result, []
        if store is not None:
            store.record_attempts(claim_no, attempts)
            store.complete(key, {"state_delta": state_delta(state, new_state), "flagged": list(flagged)}, deps.clock())
        return {"state": new_state, "attempts": attempts, "flagged": list(flagged)}

    # ---------------------------------------------------------------- intent (+ safety layer 1)
    def intent_body(state: AgentState) -> AgentState:
        gate = check_input(state.query)
        intent = classify(state.query, state.session_entities)
        if gate.decision is not SafetyDecision.allow:
            return _escalate(state, gate.reason_codes, gate.detail, intent=intent, safety_result=gate)
        if intent.type is IntentType.high_risk:
            sr = SafetyResult(
                decision=SafetyDecision.escalate,
                reason_codes=(ReasonCode.high_risk_medical,),
                detail=f"{INTENT_VERSION}: high-risk intent (INV-SAF-01)",
                checker_version=SAFETY_VERSION,
            )
            return _escalate(state, sr.reason_codes, sr.detail, intent=intent, safety_result=sr)
        if intent.type is IntentType.unclear:
            # one clarification turn belongs to the session layer (M3); without it the run escalates (5.3)
            return _escalate(
                state, (ReasonCode.intent_unclear,), f"{INTENT_VERSION}: query too short or empty", intent=intent
            )
        return state.advance(intent=intent)

    def intent_node(hs: HarnessState) -> dict[str, Any]:
        return guarded("intent", hs, _key(hs["state"], "intent"), intent_body)

    # ---------------------------------------------------------------- retrieve (+ safety layer 2, budget trim)
    def retrieve_body(state: AgentState) -> tuple[AgentState, list[str]]:
        outcome = deps.retrieval.retrieve(
            RetrievalRequest(
                query=state.query,
                user=state.user,
                historical_requested=state.historical_requested,
                as_of=deps.as_of,
                session_entities=state.session_entities,
            )
        )
        kept, flagged = screen_evidence(outcome.evidence)
        reserve = deps.answer_max_output_tokens + ANSWER_PROMPT_RESERVE
        fit: list[Evidence] = []
        used = state.budget.used
        for e in kept:
            cost = estimate_tokens(e.text)
            if used + cost + reserve > state.budget.limit:
                break
            fit.append(e)
            used += cost
        new_state = state.advance(
            rewritten_queries=outcome.rewritten_queries,
            candidates=outcome.candidates[:MAX_CANDIDATES],
            evidence=tuple(fit),
            budget=TokenBudget(limit=state.budget.limit, used=used),
        )
        if kept and not fit:
            return _escalate(
                new_state, (ReasonCode.budget_exceeded,), "no evidence fits the trace budget (INV-HAR-08)"
            ), list(flagged)
        if outcome.degraded and len(fit) < specs["retrieve"].min_evidence_when_degraded:
            return _escalate(
                new_state,
                (ReasonCode.system_failure,),
                f"degraded retrieval below evidence threshold: {outcome.detail}",
            ), list(flagged)
        return new_state, list(flagged)

    def retrieve_node(hs: HarnessState) -> dict[str, Any]:
        return guarded("retrieve", hs, _key(hs["state"], "retrieve"), retrieve_body)

    # ---------------------------------------------------------------- verify (evidence stage)
    def verify_body(state: AgentState) -> AgentState:
        # an empty evidence set is not decided here: the Safety node knows whether layer 2 dropped everything
        return state.advance(verify_result=verify_evidence(state.query, state.evidence))

    def verify_node(hs: HarnessState) -> dict[str, Any]:
        state = hs["state"]
        return guarded(
            "verify", hs, _key(state, "verify", evidence=[e.citation.chunk_id for e in state.evidence]), verify_body
        )

    # ---------------------------------------------------------------- safety (decision point)
    def safety_node(hs: HarnessState) -> dict[str, Any]:
        state = hs["state"]
        flagged = list(hs.get("flagged", []))

        def body(s: AgentState) -> AgentState:
            assert s.intent is not None
            sr = decide(s.intent, s.verify_result, s.evidence, flagged)
            new_state = s.advance(safety_result=sr)
            if sr.decision is not SafetyDecision.allow:
                return _escalate(new_state, sr.reason_codes, sr.detail)
            return new_state

        return guarded(
            "safety", hs, _key(state, "safety", evidence=[e.citation.chunk_id for e in state.evidence]), body
        )

    # ---------------------------------------------------------------- answer (+ re-verification, safety layer 3)

    def answer_node(hs: HarnessState) -> dict[str, Any]:
        state = hs["state"]
        return guarded(
            "answer",
            hs,
            _key(
                state, "answer", evidence=[e.citation.chunk_id for e in state.evidence], model=answer_model(state, deps)
            ),
            lambda state: generate_answer(state, deps),
        )

    # ---------------------------------------------------------------- escalate (sink)
    def escalate_body(state: AgentState) -> AgentState:
        if state.escalation is None:
            raise AssertionError("escalate node reached without an escalation")
        return state

    def escalate_node(hs: HarnessState) -> dict[str, Any]:
        return guarded("escalate", hs, _key(hs["state"], "escalate"), escalate_body)

    return {
        "intent": intent_node,
        "retrieve": retrieve_node,
        "verify": verify_node,
        "safety": safety_node,
        "answer": answer_node,
        "escalate": escalate_node,
    }
