"""Trusted read-only whole-operation estimates. No gateway, reservations or billing entries."""

from __future__ import annotations

from pydantic import Field

from medops.core.canonical import canonical_hash
from medops.infrastructure.llm.execution_budget import PRICES, CallEstimate, estimate_request
from medops.infrastructure.llm.gateway import GatewayModel, ModelRequest, PriceTable

CALL_PLAN_VERSION = "model-call-plan-v1+original-retry-bound"


class ModelCallPlan(GatewayModel):
    # Requests are built by the actual server handlers, never supplied by the planner.
    requests: tuple[ModelRequest, ...] = Field(default=(), max_length=20)
    max_attempts: int = Field(default=1, ge=1, le=3, strict=True)

    def estimate(self, prices: PriceTable = PRICES) -> CallEstimate:
        items = tuple(estimate_request(r, prices) for r in self.requests)
        return CallEstimate(
            tokens=sum(i.tokens for i in items) * self.max_attempts,
            cost_usd=sum(i.cost_usd for i in items) * self.max_attempts,
        )

    def audit_record(self, prices: PriceTable = PRICES) -> dict:
        estimate = self.estimate(prices)
        inputs = {
            "version": CALL_PLAN_VERSION,
            "requests": [r.model_dump(mode="json", exclude={"call"}) for r in self.requests],
            "max_attempts": self.max_attempts,
            "max_model_calls": len(self.requests) * self.max_attempts,
            "estimated_tokens": estimate.tokens,
            "estimated_cost_usd": estimate.cost_usd,
        }
        return {**inputs, "plan_sha256": canonical_hash(inputs)}
