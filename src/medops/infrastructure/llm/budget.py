"""Spend ledger and the budgeted gateway wrapper (ADR-0010 monthly cap; M2-06 groundwork).

The monthly cap is an operational stop, not a per-trace budget: when the month's recorded spend plus the
worst case of the next call would exceed the cap, the call is refused with `BudgetExceeded` and the harness
escalates (`budget_exceeded`). Nothing is silently downgraded (INV-HAR-08). The in-memory ledger is for
single-process runs and tests; a database-backed ledger arrives with M3 persistence.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from medops.infrastructure.llm.gateway import (
    BudgetExceeded,
    ModelGateway,
    ModelRequest,
    ModelResponse,
    PriceTable,
)


class SpendLedger(Protocol):
    def month_total(self, month: str) -> float: ...

    def record(self, month: str, cost_usd: float) -> float: ...


class InMemorySpendLedger:
    def __init__(self) -> None:
        self._totals: dict[str, float] = {}
        self._lock = threading.Lock()

    def month_total(self, month: str) -> float:
        with self._lock:
            return self._totals.get(month, 0.0)

    def record(self, month: str, cost_usd: float) -> float:
        if cost_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._lock:
            self._totals[month] = self._totals.get(month, 0.0) + cost_usd
            return self._totals[month]


def month_key(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m")


class BudgetedGateway:
    """Wraps a gateway with the monthly cap: worst-case pre-check, then record the real cost."""

    def __init__(
        self,
        inner: ModelGateway,
        *,
        prices: PriceTable,
        ledger: SpendLedger,
        monthly_cap_usd: float,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if monthly_cap_usd < 0:
            raise ValueError("monthly cap cannot be negative")
        self._inner = inner
        self._prices = prices
        self._ledger = ledger
        self._cap = monthly_cap_usd
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def provider(self) -> str:
        return self._inner.provider

    @property
    def monthly_cap_usd(self) -> float:
        return self._cap

    def complete(self, request: ModelRequest) -> ModelResponse:
        month = month_key(self._clock())
        spent = self._ledger.month_total(month)
        worst = self._prices.worst_case_usd(request)
        if spent + worst > self._cap:
            raise BudgetExceeded(
                f"monthly LLM cap {self._cap:.2f} USD would be exceeded: spent {spent:.4f}, next call up to {worst:.4f}"
            )
        response = self._inner.complete(request)
        self._ledger.record(month, response.cost_usd)
        return response
