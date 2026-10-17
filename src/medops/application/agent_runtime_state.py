"""Private durable Agent execution bodies and conservative receipt reconciliation.

These are encrypted by the runtime store. They never authenticate a user, grant
new budget, run tools, or turn a finish request into business completion.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from medops.application.agent_contracts import context_binding, validate_run_snapshot
from medops.application.agent_loop_state import LoopState, rebuild_loop_state
from medops.application.agent_planning import PlannerConfig
from medops.core.canonical import canonical_hash
from medops.core.money import usd_to_microusd
from medops.domain.agent_actions import AgentModel
from medops.domain.agent_execution import AgentBudget, AgentContext, BoundAction, PVAgentRun, utc_time
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, PendingAllowance
from medops.infrastructure.llm.execution_budget import BudgetSnapshot
from medops.infrastructure.llm.gateway import ModelCall, ModelCallReceipt, ModelRequest, ModelResponse

RUNTIME_STATE_VERSION: Final = "pv-agent-runtime-v1"


def request_call(request: ModelRequest) -> ModelCall:
    if request.call is None:
        raise ValueError("invalid_agent_call_owner")
    return request.call


def run_with_budget(run: PVAgentRun, snapshot: BudgetSnapshot) -> PVAgentRun:
    return validate_run_snapshot(
        run.model_copy(
            update={
                "budget": AgentBudget(
                    accounted_tokens=snapshot.accounted_tokens,
                    reserved_tokens=snapshot.reserved_tokens,
                    accounted_cost_microusd=usd_to_microusd(snapshot.accounted_cost_usd),
                    reserved_cost_microusd=usd_to_microusd(snapshot.reserved_cost_usd),
                )
            }
        )
    )


def owned_request(request: ModelRequest, context: AgentContext) -> None:
    call = request.call
    if call is None or (call.run_id, call.trace_id) != (str(context.identity.run_id), context.identity.trace_id):
        raise ValueError("invalid_agent_call_owner")
    UUID(call.call_id)
    segments = (call.attempt_id or "").split("/")
    if str(context.identity.attempt_id) not in segments or not any(
        segment.startswith(("decision:", "action:", "final:")) for segment in segments
    ):
        raise ValueError("invalid_agent_call_owner")
    if (call.purpose, call.requested_model) != (request.purpose, request.model_id):
        raise ValueError("invalid_agent_call_owner")


def owned_receipt(request: ModelRequest, receipt: ModelCallReceipt) -> None:
    call = request.call
    if call is None or call.model_dump(exclude={"reservation_id"}) != receipt.call.model_dump(
        exclude={"reservation_id"}
    ):
        raise ValueError("invalid_agent_call_receipt")
    if receipt.usage is not None and receipt.actual_cost_usd is None:
        raise ValueError("invalid_agent_call_receipt")
    if receipt.actual_cost_usd is not None and receipt.accounted_cost_usd + 1e-12 < receipt.actual_cost_usd:
        raise ValueError("invalid_agent_call_receipt")


class PlanningFrame(AgentModel):
    decision_id: UUID
    request: ModelRequest
    receipt: ModelCallReceipt | None
    response: ModelResponse | None
    invalid: bool = Field(strict=True)
    deadline_at: datetime

    _utc = field_validator("deadline_at")(utc_time)

    @model_validator(mode="after")
    def consistent(self) -> PlanningFrame:
        if self.receipt is not None:
            owned_receipt(self.request, self.receipt)
        if self.response is not None and self.receipt is None:
            raise ValueError("invalid_agent_planning_frame")
        return self


class PendingTool(AgentModel):
    action: BoundAction
    admitted_at: datetime
    admission_budget: AgentBudget

    _utc = field_validator("admitted_at")(utc_time)


class RuntimeBody(AgentModel):
    version: Literal["pv-agent-runtime-v1"]
    run: PVAgentRun
    config: PlannerConfig
    loop: LoopState | None
    frame: PlanningFrame | None
    tool: PendingTool | None

    @model_validator(mode="after")
    def consistent(self) -> RuntimeBody:
        run = validate_run_snapshot(self.run)
        if run.status != "running":
            raise ValueError("invalid_agent_runtime")
        if self.loop is None:
            if run.decisions_consumed or self.frame is not None or self.tool is not None:
                raise ValueError("invalid_agent_runtime")
        else:
            if self.loop.run != run or self.loop.config != self.config:
                raise ValueError("invalid_agent_runtime")
            rebuild_loop_state(self.loop, expected_run=run, config=self.config)
        if self.frame is not None:
            owned_request(self.frame.request, run.context)
            if f"decision:{self.frame.decision_id}" not in (request_call(self.frame.request).attempt_id or "").split(
                "/"
            ):
                raise ValueError("invalid_agent_runtime")
        if self.tool is not None:
            action = self.tool.action
            if (
                self.loop is None
                or self.loop.phase != "planning_returned"
                or self.frame is None
                or action.action_id != self.frame.decision_id
                or action.decision_index != run.decisions_consumed
                or action.binding != context_binding(run.context)
            ):
                raise ValueError("invalid_agent_runtime")
        return self

    def with_budget(self, state: FrozenBudgetState) -> RuntimeBody:
        run = run_with_budget(self.run, state.snapshot)
        loop = self.loop.model_copy(update={"run": run}) if self.loop is not None else None
        return RuntimeBody.model_validate(self.model_copy(update={"run": run, "loop": loop}).model_dump(mode="json"))


class DurableCall(AgentModel):
    request: ModelRequest
    allowance: PendingAllowance
    receipt: ModelCallReceipt | None
    response: ModelResponse | None
    audit_entry: dict[str, JsonValue]

    @model_validator(mode="after")
    def consistent(self) -> DurableCall:
        if self.request.call is None or self.allowance.call_id != self.request.call.call_id:
            raise ValueError("invalid_agent_durable_call")
        if self.receipt is not None:
            owned_receipt(self.request, self.receipt)
        if self.response is not None and self.receipt is None:
            raise ValueError("invalid_agent_durable_call")
        entry = self.audit_entry
        if entry.get("call_id") != (self.request.call.call_id if self.request.call else None):
            raise ValueError("invalid_agent_durable_call")
        body = entry.get("request")
        if not isinstance(body, dict) or canonical_hash(body) != entry.get("request_sha256"):
            raise ValueError("invalid_agent_durable_call")
        actual = ModelRequest.model_validate(body)
        if actual.model_dump(exclude={"timeout_s"}) != self.request.model_dump(exclude={"timeout_s"}):
            raise ValueError("invalid_agent_durable_call")
        return self


def reconcile_budget(state: FrozenBudgetState, calls: tuple[DurableCall, ...]) -> FrozenBudgetState:
    """Resolve only saved pending allowances with matching durable receipts.

    No receipt stays pending and stops recovery. Unknown usage stays conservative;
    neither known fees nor settled IDs are removed. There is no provider resend.
    """
    data = state.model_dump(mode="json")
    by_id = {c.request.call.call_id: c for c in calls if c.request.call is not None}
    if len(by_id) != len(calls):
        raise ValueError("invalid_agent_call_journal")
    snapshot = data["snapshot"]
    remaining = []
    for pending in state.pending:
        record = by_id.get(pending.call_id)
        receipt = record.receipt if record else None
        if receipt is None:
            remaining.append(pending.model_dump(mode="json"))
            continue
        known = receipt.usage.total_tokens if receipt.usage is not None else 0
        snapshot["accounted_tokens"] += (
            known if receipt.usage is not None else pending.tokens if receipt.provider_started else 0
        )
        snapshot["known_tokens"] += known
        snapshot["accounted_cost_usd"] += receipt.accounted_cost_usd
        snapshot["known_cost_usd"] += receipt.actual_cost_usd or 0
        snapshot["calls"] += int(receipt.provider_started)
        data["settled"].append(pending.call_id)
    data["pending"] = remaining
    snapshot["reserved_tokens"] = sum(p["tokens"] for p in remaining)
    snapshot["reserved_cost_usd"] = sum(p["cost_usd"] for p in remaining)
    if snapshot["blocked_reason"] is None:
        if (
            snapshot["accounted_tokens"] + snapshot["reserved_tokens"] + snapshot["protected_tokens"]
            > snapshot["limits"]["token_limit"]
        ):
            snapshot["blocked_reason"] = "tokens"
        elif (
            snapshot["accounted_cost_usd"] + snapshot["reserved_cost_usd"] + snapshot["protected_cost_usd"]
            > snapshot["limits"]["cost_limit_usd"] + 1e-12
        ):
            snapshot["blocked_reason"] = "cost"
    return FrozenBudgetState.model_validate(data)


def verify_accounting(state: FrozenBudgetState, calls: tuple[DurableCall, ...], context: AgentContext) -> None:
    """Actual admitted call lineage, not just equality of four caller counters."""
    by_id = {c.allowance.call_id: c for c in calls}
    if len(by_id) != len(calls) or set(by_id) != set(state.settled) | {p.call_id for p in state.pending}:
        raise ValueError("invalid_agent_accounting_lineage")
    tokens = known_tokens = started = 0
    cost = known_cost = 0.0
    for call_id, record in by_id.items():
        owned_request(record.request, context)
        if call_id not in state.settled:
            if record.allowance not in state.pending:
                raise ValueError("invalid_agent_accounting_lineage")
            continue
        receipt = record.receipt
        if receipt is None:
            raise ValueError("incomplete_agent_accounting_lineage")
        known = receipt.usage.total_tokens if receipt.usage is not None else 0
        known_tokens += known
        tokens += known if receipt.usage is not None else record.allowance.tokens if receipt.provider_started else 0
        started += int(receipt.provider_started)
        cost += receipt.accounted_cost_usd
        known_cost += receipt.actual_cost_usd or 0
    s = state.snapshot
    if (s.accounted_tokens, s.known_tokens, s.calls) != (tokens, known_tokens, started) or not (
        math.isclose(s.accounted_cost_usd, cost, rel_tol=0, abs_tol=1e-10)
        and math.isclose(s.known_cost_usd, known_cost, rel_tol=0, abs_tol=1e-10)
    ):
        raise ValueError("invalid_agent_accounting_lineage")
