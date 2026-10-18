"""Fixed metadata projection for Agent spans; never export model-supplied text.

The encrypted runtime journal remains the authoritative audit. These helpers
neither read facts nor admit calls, and a handoff is not a business completion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from medops.application.agent_terminal import AgentDelivery
from medops.domain.agent_execution import TERMINAL_REASONS, StopReason

if TYPE_CHECKING:
    from medops.bootstrap.agent_driver import PgAgentDriver


def execution_attributes(driver: PgAgentDriver, *, recovered: bool) -> dict[str, str | int | bool]:
    context = driver.context
    identity, versions = context.identity, context.versions
    return {
        "medops.case_id": str(identity.case_id),
        "medops.task_id": str(identity.task_id),
        "medops.run_id": str(identity.run_id),
        "medops.agent.attempt_id": str(identity.attempt_id),
        "medops.agent.lease_generation": driver.lease.generation,
        "medops.agent.recovered": recovered,
        "medops.agent.planning_prompt_sha256": versions.planning_prompt_sha256,
        "medops.agent.tool_contract_sha256": versions.tool_contract_sha256,
        "medops.agent.verification_policy_sha256": versions.verification_policy_sha256,
        "medops.agent.fact_conditions_sha256": versions.fact_conditions_sha256,
        "medops.agent.fact_database_id": str(versions.fact_database_id),
        "medops.agent.token_limit": context.profile.token_cap,
        "medops.agent.cost_limit_microusd": context.profile.cost_cap_microusd,
        "medops.agent.decision_limit": context.profile.max_decision_steps,
    }


def execution_summary(
    driver: PgAgentDriver,
    delivery: AgentDelivery | None,
    error: BaseException | None,
    *,
    calls_at_start: int | None = None,
    handoff_reason: StopReason | None = None,
) -> dict[str, str | int | float | bool]:
    snapshot = driver.root.snapshot()
    result: dict[str, str | int | float | bool] = {
        "medops.agent.business_committed": delivery is not None,
        "medops.agent.business_status": delivery.run.status if delivery is not None else "unconfirmed",
        "medops.agent.decisions_consumed": driver.head.body.run.decisions_consumed,
        "medops.agent.model_calls_total": snapshot.calls,
        "medops.agent.accounted_tokens": snapshot.accounted_tokens,
        "medops.agent.known_tokens": snapshot.known_tokens,
        "medops.agent.reserved_tokens": snapshot.reserved_tokens,
        "medops.agent.accounted_cost_usd": snapshot.accounted_cost_usd,
        "medops.agent.known_cost_usd": snapshot.known_cost_usd,
        "medops.agent.reserved_cost_usd": snapshot.reserved_cost_usd,
        "medops.agent.exception_raised": error is not None,
    }
    if calls_at_start is not None:
        result["medops.agent.model_calls_this_session"] = snapshot.calls - calls_at_start
    if handoff_reason is not None:
        result["medops.agent.handoff_reason"] = handoff_reason
    if delivery is not None:
        result["medops.agent.stop_reason"] = delivery.material.reason
    if error is not None:
        result["error_code"] = "agent_execution_error"
    elif delivery is not None and delivery.run.status == "failed":
        result["error_code"] = delivery.material.reason
    elif delivery is None and handoff_reason in TERMINAL_REASONS["failed"]:
        result["error_code"] = str(handoff_reason)
    return result
