"""Gateway contract: typed request/response, price table and the error types the node policy reacts to.

Design rules (baseline 2.4, 5.7; ADR-0010):
- every call names its `purpose` (the node) and a pinned `model_id`; the response carries provider, model,
  usage, cost and the provider's response identifiers so that the trace records the actual version set;
- retrieved documents are passed as user-role data blocks (INV-HAR-07); nothing here rewrites roles;
- timeouts are per call and mandatory (INV-HAR-04); the adapter never retries by itself, the node policy does;
- cost is computed locally from a fixed price table, so a call to an unpriced model is refused before it runs.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from medops.core.errors import ErrorCode, InfrastructureError

Role = Literal["system", "user"]


class GatewayModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class Message(GatewayModel):
    role: Role
    content: str = Field(min_length=1)


class ModelRequest(GatewayModel):
    purpose: str = Field(min_length=1)  # node / call purpose, recorded on the trace
    model_id: str = Field(min_length=1)
    messages: tuple[Message, ...] = Field(min_length=1)
    max_output_tokens: int = Field(gt=0, le=8192)
    temperature: float = Field(default=0.0, ge=0.0, le=1.0)
    json_schema: dict[str, Any] | None = None  # strict structured output when set
    timeout_s: float = Field(default=30.0, gt=0, le=300)

    @property
    def prompt_chars(self) -> int:
        return sum(len(m.content) for m in self.messages)


class ModelUsage(GatewayModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ModelResponse(GatewayModel):
    text: str
    parsed: dict[str, Any] | None = None
    usage: ModelUsage
    cost_usd: float = Field(ge=0)
    provider: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    response_id: str | None = None
    system_fingerprint: str | None = None
    latency_ms: float = Field(ge=0)
    truncated: bool = False  # the provider stopped at max_output_tokens: never treat as a complete answer


class ModelGateway(Protocol):
    @property
    def provider(self) -> str: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...


# ------------------------------------------------------------------------------------ errors


class ModelTimeout(InfrastructureError):
    def __init__(self, detail: str = "model call timed out") -> None:
        super().__init__(ErrorCode.dependency_timeout, detail=detail, retryable=True)


class ModelUnavailable(InfrastructureError):
    def __init__(self, detail: str = "model provider unavailable", *, retryable: bool = True) -> None:
        super().__init__(ErrorCode.dependency_unavailable, detail=detail, retryable=retryable)


class ModelOutputInvalid(Exception):
    """The provider answered, but not in the requested structure. Not retryable: the same prompt produces the
    same failure at temperature 0, and guessing a repair would be an unverified answer path."""


class BudgetExceeded(Exception):
    """A call would exceed the monthly cap (ADR-0010) or the per-trace budget (INV-HAR-08)."""


# ------------------------------------------------------------------------------------ prices


class ModelPrice(GatewayModel):
    input_per_mtok: float = Field(ge=0)
    cached_input_per_mtok: float = Field(ge=0)
    output_per_mtok: float = Field(ge=0)


# ADR-0010 §依据 (official price pages, 2026-09-23). Extend when a model is admitted; never guess a price.
OPENAI_PRICES: Mapping[str, ModelPrice] = {
    "gpt-6-luna": ModelPrice(input_per_mtok=0.10, cached_input_per_mtok=0.01, output_per_mtok=0.50),
    "gpt-6-sol": ModelPrice(input_per_mtok=2.00, cached_input_per_mtok=0.20, output_per_mtok=10.00),
    "gpt-6-astra": ModelPrice(input_per_mtok=10.00, cached_input_per_mtok=1.00, output_per_mtok=50.00),
    "gpt-5.4-mini": ModelPrice(input_per_mtok=0.75, cached_input_per_mtok=0.075, output_per_mtok=4.50),
    "gpt-5.4-nano": ModelPrice(input_per_mtok=0.20, cached_input_per_mtok=0.02, output_per_mtok=1.25),
}


class PriceTable:
    def __init__(self, prices: Mapping[str, ModelPrice]) -> None:
        self._prices = dict(prices)

    def require(self, model_id: str) -> ModelPrice:
        try:
            return self._prices[model_id]
        except KeyError:
            raise ModelUnavailable(
                f"model {model_id!r} has no price entry; admit it in the price table first", retryable=False
            ) from None

    def cost_usd(self, model_id: str, usage: ModelUsage) -> float:
        p = self.require(model_id)
        uncached = max(usage.input_tokens - usage.cached_input_tokens, 0)
        cost = (
            uncached * p.input_per_mtok
            + usage.cached_input_tokens * p.cached_input_per_mtok
            + usage.output_tokens * p.output_per_mtok
        ) / 1_000_000
        return round(cost, 8)

    def worst_case_usd(self, request: ModelRequest) -> float:
        """Upper bound before the call: all prompt tokens uncached plus the full output allowance."""
        p = self.require(request.model_id)
        prompt = estimate_tokens("".join(m.content for m in request.messages))
        return (prompt * p.input_per_mtok + request.max_output_tokens * p.output_per_mtok) / 1_000_000


def estimate_tokens(text: str) -> int:
    """Conservative local estimate: one token per CJK character, one per four other characters (rounded up).
    Used for budgets before a provider reports real usage; never for billing."""
    cjk = sum(1 for ch in text if "㐀" <= ch <= "鿿" or "豈" <= ch <= "﫿")
    other = len(text) - cjk
    return cjk + math.ceil(other / 4)
