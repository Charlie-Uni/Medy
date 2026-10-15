"""One shared execution allowance across nesting, translation threads and logical call retries."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from medops.core.deadline import CURRENT_DEADLINE, DeadlineExceeded, check_deadline, deadline_scope, remaining_timeout
from medops.infrastructure.llm.accounting import capture_call, check_call_ownership, new_call, publish_receipt
from medops.infrastructure.llm.gateway import (
    OPENAI_PRICES,
    BudgetExceeded,
    GatewayModel,
    ModelCallReceipt,
    ModelOutputInvalid,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    PriceTable,
)

DEFAULT_EXECUTION_TOKENS = 12_000
EXECUTION_BUDGET_VERSION = "execution-budget-v2+utf8-preflight+protected-headroom"
PRICES = PriceTable(OPENAI_PRICES)

if TYPE_CHECKING:
    from medops.core.config import Settings


class ExecutionLimits(GatewayModel):
    token_limit: int = Field(default=DEFAULT_EXECUTION_TOKENS, gt=0)
    cost_limit_usd: float = Field(ge=0)
    timeout_s: float = Field(gt=0)


class ExecutionBudgetExceeded(BudgetExceeded):
    def __init__(self, dimension: str) -> None:
        self.dimension = dimension
        super().__init__(f"execution {dimension} budget exhausted")


class BudgetProtection(GatewayModel):
    """Unspent headroom, not provider usage, a bill or a pending call reservation.

    Trusted execution owners may only increase this floor. Consuming it in a
    final verification phase requires a separate approved owner integration.
    """

    tokens: int = Field(default=0, ge=0, strict=True)
    cost_usd: float = Field(default=0, ge=0, strict=True)


class BudgetSnapshot(GatewayModel):
    limits: ExecutionLimits
    accounted_tokens: int = Field(ge=0)
    known_tokens: int = Field(ge=0)
    reserved_tokens: int = Field(ge=0)
    accounted_cost_usd: float = Field(ge=0)
    known_cost_usd: float = Field(ge=0)
    reserved_cost_usd: float = Field(ge=0)
    calls: int = Field(ge=0)
    blocked_reason: str | None = None
    protected_tokens: int = Field(default=0, ge=0)
    protected_cost_usd: float = Field(default=0, ge=0)


@dataclass(frozen=True)
class CallAllowance:
    call_id: str
    tokens: int
    cost_usd: float


def request_tokens(request: ModelRequest) -> int:
    """Byte-based preflight, including schema/framing and output; not provider-reported billing usage.

    Avoid the old chars/4 heuristic for admission. Provider-side hidden framing can still differ: an
    unexpectedly larger reported usage is retained, stops the execution and never becomes an answer.
    """
    schema = json.dumps(request.json_schema, ensure_ascii=False, separators=(",", ":")) if request.json_schema else ""
    prompt = sum(len(m.content.encode("utf-8")) + 32 for m in request.messages)
    return prompt + len(schema.encode("utf-8")) + 128 + request.max_output_tokens


def allowance(request: ModelRequest, prices: PriceTable = PRICES) -> CallAllowance:
    assert request.call is not None
    tokens = request_tokens(request)
    input_tokens = tokens - request.max_output_tokens
    cost = prices.cost_usd(
        request.model_id, ModelUsage(input_tokens=input_tokens, output_tokens=request.max_output_tokens)
    )
    return CallAllowance(request.call.call_id, tokens, cost)


def default_limits(*, timeout_s: float, token_limit: int = DEFAULT_EXECUTION_TOKENS) -> ExecutionLimits:
    # Owner-confirmed 2026-10-11: derive the compatible fee bound from the admitted fixed price table.
    highest = max(max(p.input_per_mtok, p.output_per_mtok, p.cached_input_per_mtok) for p in OPENAI_PRICES.values())
    return ExecutionLimits(
        token_limit=token_limit, cost_limit_usd=token_limit * highest / 1_000_000, timeout_s=timeout_s
    )


def configured_limits(settings: Settings, *, timeout_s: float | None = None) -> ExecutionLimits:
    return ExecutionLimits(
        token_limit=settings.llm_execution_token_limit,
        cost_limit_usd=settings.llm_execution_cost_limit_usd,
        timeout_s=min(settings.llm_execution_timeout_s, timeout_s)
        if timeout_s is not None
        else settings.llm_execution_timeout_s,
    )


class ExecutionBudget:
    def __init__(self, limits: ExecutionLimits) -> None:
        self._limits = limits
        self._expires_at: float | None = None
        self._tokens = self._known_tokens = self._calls = 0
        self._cost = self._known_cost = 0.0
        self._active: dict[str, CallAllowance] = {}
        self._settled: set[str] = set()
        self._blocked: str | None = None
        self._protection = BudgetProtection()
        self._lock = threading.Lock()

    @property
    def limits(self) -> ExecutionLimits:
        return self._limits

    def protection(self) -> BudgetProtection:
        with self._lock:
            return self._protection

    def protect_remaining(self, protection: BudgetProtection) -> None:
        """Atomically keep headroom across all threads, nested scopes and meters.

        Protection persists on this budget after context exit; a child cannot
        relax it or re-enter a fresh spending allowance. No fake call/fee entry.
        """
        protection = BudgetProtection.model_validate(protection.model_dump(mode="python", warnings=False))
        with self._lock:
            protected = BudgetProtection(
                tokens=max(self._protection.tokens, protection.tokens),
                cost_usd=max(self._protection.cost_usd, protection.cost_usd),
            )
            reason = self._blocked or self._dimension(protection=protected)
            if reason is not None:
                self._blocked = reason
                raise ExecutionBudgetExceeded(reason)
            self._protection = protected

    def remaining_timeout(self, timeout_s: float) -> float:
        with self._lock:
            now = time.monotonic()
            if self._expires_at is None:
                self._expires_at = now + min(self.limits.timeout_s, timeout_s)
                parent = CURRENT_DEADLINE.get()
                if parent is not None:
                    self._expires_at = min(self._expires_at, parent.expires_at)
            remaining = self._expires_at - now
        if remaining <= 0:
            raise DeadlineExceeded()
        return remaining

    def snapshot(self) -> BudgetSnapshot:
        with self._lock:
            return BudgetSnapshot(
                limits=self.limits,
                accounted_tokens=self._tokens,
                known_tokens=self._known_tokens,
                reserved_tokens=sum(a.tokens for a in self._active.values()),
                accounted_cost_usd=self._cost,
                known_cost_usd=self._known_cost,
                reserved_cost_usd=sum(a.cost_usd for a in self._active.values()),
                calls=self._calls,
                blocked_reason=self._blocked,
                protected_tokens=self._protection.tokens,
                protected_cost_usd=self._protection.cost_usd,
            )

    def check(self) -> None:
        with self._lock:
            if self._blocked is not None:
                raise ExecutionBudgetExceeded(self._blocked)

    def fits(self, item: CallAllowance) -> bool:
        with self._lock:
            return self._blocked is None and self._dimension(item) is None

    def _dimension(
        self, item: CallAllowance | None = None, *, protection: BudgetProtection | None = None
    ) -> Literal["tokens", "cost"] | None:
        protected = protection or self._protection
        if (
            self._tokens
            + sum(a.tokens for a in self._active.values())
            + (item.tokens if item else 0)
            + protected.tokens
            > self.limits.token_limit
        ):
            return "tokens"
        if (
            self._cost
            + sum(a.cost_usd for a in self._active.values())
            + (item.cost_usd if item else 0)
            + protected.cost_usd
            > self.limits.cost_limit_usd + 1e-12
        ):
            return "cost"
        return None

    def reserve(self, item: CallAllowance) -> None:
        with self._lock:
            if item.call_id in self._active or item.call_id in self._settled:
                raise ValueError("execution call identity was reused")
            reason = self._blocked or self._dimension(item)
            if reason is not None:
                self._blocked = reason
                raise ExecutionBudgetExceeded(reason)
            self._active[item.call_id] = item

    def settle(self, item: CallAllowance, receipt: ModelCallReceipt) -> None:
        with self._lock:
            if receipt.call.call_id != item.call_id or self._active.pop(item.call_id, None) != item:
                raise ValueError("execution allowance does not match receipt")
            self._settled.add(item.call_id)
            known = receipt.usage.total_tokens if receipt.usage is not None else 0
            self._tokens += known if receipt.usage is not None else item.tokens if receipt.provider_started else 0
            self._known_tokens += known
            self._cost += receipt.accounted_cost_usd
            self._known_cost += receipt.actual_cost_usd or 0
            self._calls += int(receipt.provider_started)
            # Zero protection keeps legacy settlement semantics. With protection,
            # a surprise over-reservation usage must also retain the final floor.
            reason: str | None = None
            if self._tokens > self.limits.token_limit:
                reason = "tokens"
            elif self._cost > self.limits.cost_limit_usd + 1e-12:
                reason = "cost"
            elif self._protection.tokens or self._protection.cost_usd:
                reason = self._dimension()
            if reason is not None:
                self._blocked = reason


_BUDGET: ContextVar[ExecutionBudget | None] = ContextVar("execution_budget", default=None)
_CALL: ContextVar[tuple[ExecutionBudget, CallAllowance] | None] = ContextVar("execution_call_allowance", default=None)


def current_budget() -> ExecutionBudget | None:
    return _BUDGET.get()


def check_execution_budget() -> None:
    budget = current_budget()
    if budget is not None:
        budget.check()


@contextmanager
def execution_scope(limits: ExecutionLimits, *, budget: ExecutionBudget | None = None) -> Iterator[ExecutionBudget]:
    parent = current_budget()
    if parent is not None and budget is not None and budget is not parent:
        raise ValueError("nested execution cannot replace its parent's allowance")
    owned = parent or budget or ExecutionBudget(limits)
    token = _BUDGET.set(owned)
    try:
        with deadline_scope(min(limits.timeout_s, owned.remaining_timeout(limits.timeout_s))):
            yield owned
    finally:
        _BUDGET.reset(token)


def admitted_cost(call_id: str) -> float | None:
    current = _CALL.get()
    return current[1].cost_usd if current is not None and current[1].call_id == call_id else None


def request_fits_budget(request: ModelRequest) -> bool:
    budget = current_budget()
    if budget is None:
        return True
    request = request.model_copy(update={"call": request.call or new_call(request, "preflight")})
    return budget.fits(allowance(request))


def complete_in_execution(
    request: ModelRequest,
    operation: Callable[[ModelRequest], ModelResponse],
    *,
    provider: str,
    prices: PriceTable = PRICES,
) -> ModelResponse:
    budget = current_budget()
    if budget is None:
        return operation(request)  # legacy standalone/offline calls retain their explicit batch/monthly caps
    call = request.call or new_call(request, provider)
    request = request.model_copy(update={"call": call})
    parent = _CALL.get()
    if parent is not None and parent[0] is budget and parent[1].call_id == call.call_id:
        return operation(request)  # nested meter/monthly gateway, one admission and one settlement
    try:
        check_deadline()
        check_call_ownership()
        check_deadline()  # ownership checking may have consumed the remaining execution time
        request = request.model_copy(update={"timeout_s": remaining_timeout(request.timeout_s)})
        item = allowance(request, prices)
    except BaseException as exc:
        publish_receipt(
            ModelCallReceipt(
                call=call,
                outcome="failed" if isinstance(exc, Exception) else "cancelled",
                provider_started=False,
                estimated_cost_usd=0,
                actual_cost_usd=0,
                accounted_cost_usd=0,
                cost_basis="not_started",
                settlement_status="not_required",
                error_type=type(exc).__name__,
            )
        )
        raise
    try:
        budget.reserve(item)
    except ExecutionBudgetExceeded:
        publish_receipt(
            ModelCallReceipt(
                call=call,
                outcome="denied",
                provider_started=False,
                estimated_cost_usd=item.cost_usd,
                actual_cost_usd=0,
                accounted_cost_usd=0,
                cost_basis="not_started",
                settlement_status="not_required",
                error_type="ExecutionBudgetExceeded",
            )
        )
        raise
    token = _CALL.set((budget, item))
    try:
        with capture_call(call.call_id) as capture:
            try:
                response = operation(request)
            except BaseException as exc:
                known = exc.model_response if isinstance(exc, ModelOutputInvalid) else None
                receipt = capture.receipt or _receipt(request, known, item, exc)
                publish_receipt(receipt)
                budget.settle(item, receipt)
                raise
            receipt = response.call_receipt or capture.receipt or _receipt(request, response, item)
            publish_receipt(receipt)
            budget.settle(item, receipt)
            budget.check()  # retain actual overage, reject the late answer and stop any further model work
            return response.model_copy(update={"call_receipt": receipt})
    finally:
        _CALL.reset(token)


def _receipt(
    request: ModelRequest, response: ModelResponse | None, item: CallAllowance, error: BaseException | None = None
) -> ModelCallReceipt:
    assert request.call is not None
    return ModelCallReceipt(
        call=request.call,
        outcome="succeeded" if error is None else "failed" if isinstance(error, Exception) else "cancelled",
        provider_started=True,
        estimated_cost_usd=item.cost_usd,
        actual_cost_usd=response.cost_usd if response else None,
        accounted_cost_usd=response.cost_usd if response else item.cost_usd,
        cost_basis="reported_usage" if response else "conservative_reservation",
        settlement_status="not_required",
        usage=response.usage if response else None,
        response_id=response.response_id if response else None,
        response_model=response.model_id if response else None,
        error_type=type(error).__name__ if error else None,
    )
