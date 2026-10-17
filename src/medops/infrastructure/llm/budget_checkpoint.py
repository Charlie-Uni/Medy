"""Strict metadata codec for a frozen root; no body, provider call or recovery authority.

The PostgreSQL consumer, not this codec, must grant the one-time handoff. Runtime
admission does not import this module, avoiding a codec/runtime dependency cycle.
"""

from __future__ import annotations

import math
import time
from typing import Annotated, Any
from uuid import UUID

from pydantic import Field, model_validator

from medops.infrastructure.llm.execution_budget import (
    BUDGET_CHECKPOINT_VERSION,
    EXECUTION_BUDGET_VERSION,
    FINALIZATION_BUDGET_VERSION,
    BudgetSnapshot,
    ExecutionBudget,
    ExecutionLimits,
    FinalizationProfile,
    current_budget,
)
from medops.infrastructure.llm.gateway import GatewayModel

Count = Annotated[int, Field(ge=0, strict=True)]
CallId = Annotated[str, Field(min_length=1, max_length=128, strict=True)]


class PendingAllowance(GatewayModel):
    call_id: CallId
    tokens: Count
    cost_usd: float = Field(ge=0, strict=True)


class FinalSlotState(GatewayModel):
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    tokens: Count
    cost_usd: float = Field(ge=0, strict=True)
    timeout_s: float = Field(gt=0, strict=True)
    used: bool = Field(strict=True)


class FinalPhaseState(GatewayModel):
    profile: FinalizationProfile
    slots: tuple[FinalSlotState, ...] = Field(max_length=60)
    token_base: Count
    cost_base: float = Field(ge=0, strict=True)
    closed: bool = Field(strict=True)


class FrozenBudgetState(GatewayModel):
    version: str
    runtime_version: str
    checkpoint_id: UUID
    snapshot: BudgetSnapshot
    pending: tuple[PendingAllowance, ...] = Field(max_length=4096)
    settled: tuple[CallId, ...] = Field(max_length=4096)
    remaining_timeout_s: float = Field(ge=0, strict=True)
    final_phase: FinalPhaseState | None

    @model_validator(mode="before")
    @classmethod
    def complete_shape(cls, value: Any) -> Any:
        # Public snapshots have compatibility defaults. A recovery image must not
        # acquire headroom by silently filling one of those missing fields.
        if not isinstance(value, dict):
            raise ValueError("invalid_budget_checkpoint")
        snapshot = value.get("snapshot")
        if not isinstance(snapshot, dict) or set(snapshot) != set(BudgetSnapshot.model_fields):
            raise ValueError("incomplete_budget_checkpoint")
        limits = snapshot.get("limits")
        if not isinstance(limits, dict) or set(limits) != set(ExecutionLimits.model_fields):
            raise ValueError("incomplete_budget_checkpoint")
        if type(limits["token_limit"]) is not int or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) for v in limits.values()
        ):
            raise ValueError("invalid_budget_checkpoint_limits")
        phase = value.get("final_phase")
        if phase is not None and (
            not isinstance(phase, dict)
            or not isinstance(phase.get("profile"), dict)
            or set(phase["profile"]) != set(FinalizationProfile.model_fields)
        ):
            raise ValueError("incomplete_budget_checkpoint")
        for key, item in snapshot.items():
            if key.endswith("tokens") or key == "calls":
                if type(item) is not int:
                    raise ValueError("invalid_budget_checkpoint_counter")
            if key.endswith("usd") and (isinstance(item, bool) or not isinstance(item, (int, float))):
                raise ValueError("invalid_budget_checkpoint_cost")
        return value

    @model_validator(mode="after")
    def consistent(self) -> FrozenBudgetState:
        s = self.snapshot
        if self.version != BUDGET_CHECKPOINT_VERSION or self.runtime_version != EXECUTION_BUDGET_VERSION:
            raise ValueError("unsupported_budget_checkpoint_version")
        ids = [p.call_id for p in self.pending]
        if len(set(ids)) != len(ids) or len(set(self.settled)) != len(self.settled) or set(ids) & set(self.settled):
            raise ValueError("duplicate_budget_checkpoint_call")
        if s.reserved_tokens != sum(p.tokens for p in self.pending) or not math.isclose(
            s.reserved_cost_usd, sum(p.cost_usd for p in self.pending), rel_tol=0, abs_tol=1e-12
        ):
            raise ValueError("inconsistent_budget_checkpoint_reservation")
        if (
            s.calls > len(self.settled)
            or s.known_tokens > s.accounted_tokens
            or self.remaining_timeout_s > s.limits.timeout_s
        ):
            raise ValueError("inconsistent_budget_checkpoint_counter")
        phase = self.final_phase
        if phase is not None and (
            phase.profile.version != FINALIZATION_BUDGET_VERSION
            or len(phase.slots) != phase.profile.max_calls
            or sum(p.tokens for p in phase.slots) != phase.profile.estimated_tokens
            or not math.isclose(
                round(sum(p.cost_usd for p in phase.slots), 8),
                phase.profile.estimated_cost_usd,
                rel_tol=0,
                abs_tol=1e-12,
            )
            or phase.token_base > s.accounted_tokens
            or phase.cost_base > s.accounted_cost_usd + 1e-12
        ):
            raise ValueError("inconsistent_final_checkpoint")
        return self


def restore_consumed_budget(state: FrozenBudgetState, *, expires_at_monotonic: float) -> ExecutionBudget:
    """Trusted consumer only, after its PostgreSQL claim has committed successfully."""
    state = FrozenBudgetState.model_validate(state.model_dump(mode="json"))
    if current_budget() is not None:
        raise ValueError("recovery cannot replace an existing execution")
    remaining = expires_at_monotonic - time.monotonic()
    if not math.isfinite(expires_at_monotonic) or not 0 < remaining <= state.remaining_timeout_s:
        raise ValueError("invalid_recovery_deadline")
    return ExecutionBudget._from_validated_state(
        state.model_dump(mode="json"), expires_at_monotonic=expires_at_monotonic
    )
