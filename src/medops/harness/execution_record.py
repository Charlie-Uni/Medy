"""Actual Harness input and content bindings, shared by Ask, Skills and diagnostic replay."""

from __future__ import annotations

from typing import Any

from medops.core.canonical import sha256_hex
from medops.core.deadline import check_deadline
from medops.core.run_artifacts import online_artifacts
from medops.domain.state import AgentState
from medops.harness.dependencies import HarnessDeps
from medops.infrastructure.llm.execution_budget import ExecutionLimits


def execution_input(state: AgentState, *, recursion_limit: int) -> dict[str, Any]:
    return {
        "query": state.query,
        "user": state.user.model_dump(mode="json"),
        "versions": state.versions.model_dump(mode="json"),
        "token_limit": state.budget.limit,
        "session_entities": [e.model_dump(mode="json") for e in state.session_entities],
        "historical_requested": state.historical_requested,
        "query_context": state.query_context.model_dump(mode="json") if state.query_context else None,
        "recursion_limit": recursion_limit,
    }


def execution_conditions(
    deps: HarnessDeps, limits: ExecutionLimits, *, shared_limits: ExecutionLimits
) -> dict[str, Any]:
    check_deadline()
    artifacts = online_artifacts()
    check_deadline()
    return {
        "artifacts": artifacts,
        "routed": dict(deps.execution_binding),
        "configuration": {
            "answer_model_id": deps.answer_model_id,
            "judge_model_id": deps.judge_model_id,
            "answer_model_by_intent": dict(deps.answer_model_by_intent),
            "answer_system_sha256": sha256_hex(deps.answer_system),
            "answer_max_output_tokens": deps.answer_max_output_tokens,
            "evidence_focus": deps.evidence_focus,
            "node_specs": {key: spec.model_dump(mode="json") for key, spec in deps.specs.items()},
            "execution_limits": limits.model_dump(mode="json"),
            "shared_execution_limits": shared_limits.model_dump(mode="json"),
        },
        "facts_scope": "observed_retrieval_not_corpus_snapshot",
        "original_conditions_available": False,
    }
