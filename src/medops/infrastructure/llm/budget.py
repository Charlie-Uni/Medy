"""Durable monthly spend reservations and the budgeted model gateway (ADR-0010).

Capacity is reserved before a provider call and settled afterwards. A provider failure is charged at the
reserved worst case because it may still be billable. A process crash leaves the reservation visible and
continues to consume capacity until an operator reconciles it, which preserves the fail-closed budget bound.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import psycopg

from medops.infrastructure.llm.gateway import BudgetExceeded, ModelGateway, ModelRequest, ModelResponse, PriceTable


@dataclass(frozen=True)
class SpendReservation:
    reservation_id: str
    month: str
    reserved_usd: float


class SpendLedger(Protocol):
    def month_total(self, month: str) -> float: ...

    def reserve(self, month: str, cost_usd: float, cap_usd: float) -> SpendReservation | None: ...

    def settle(self, reservation: SpendReservation, actual_usd: float) -> float: ...


class InMemorySpendLedger:
    """Thread-safe test ledger with the same reservation contract as PostgreSQL."""

    def __init__(self) -> None:
        self._totals: dict[str, float] = {}
        self._reserved: dict[str, float] = {}
        self._reservations: dict[str, tuple[str, float, float | None]] = {}
        self._lock = threading.Lock()

    def month_total(self, month: str) -> float:
        with self._lock:
            return self._totals.get(month, 0.0)

    def reserve(self, month: str, cost_usd: float, cap_usd: float) -> SpendReservation | None:
        if cost_usd < 0 or cap_usd < 0:
            raise ValueError("cost and cap cannot be negative")
        with self._lock:
            if self._totals.get(month, 0.0) + self._reserved.get(month, 0.0) + cost_usd > cap_usd:
                return None
            reservation_id = str(uuid.uuid4())
            self._reserved[month] = self._reserved.get(month, 0.0) + cost_usd
            self._reservations[reservation_id] = (month, cost_usd, None)
            return SpendReservation(reservation_id, month, cost_usd)

    def settle(self, reservation: SpendReservation, actual_usd: float) -> float:
        if actual_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._lock:
            current = self._reservations.get(reservation.reservation_id)
            if current is None or current[:2] != (reservation.month, reservation.reserved_usd):
                raise ValueError("unknown or mismatched spend reservation")
            if current[2] is not None:
                if current[2] != actual_usd:
                    raise ValueError("spend reservation already settled differently")
                return self._totals.get(reservation.month, 0.0)
            self._reserved[reservation.month] -= reservation.reserved_usd
            self._totals[reservation.month] = self._totals.get(reservation.month, 0.0) + actual_usd
            self._reservations[reservation.reservation_id] = (*current[:2], actual_usd)
            return self._totals[reservation.month]


class PostgresSpendLedger:
    """Short independent transactions shared by every API and evaluation process."""

    def __init__(self, dsn: str, *, connect_timeout_s: int = 5, statement_timeout_ms: int = 5000) -> None:
        self._dsn = dsn
        self._connect_timeout_s = connect_timeout_s
        self._statement_timeout_ms = statement_timeout_ms

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(
            self._dsn,
            connect_timeout=self._connect_timeout_s,
            options=f"-c statement_timeout={self._statement_timeout_ms}",
        )

    def month_total(self, month: str) -> float:
        with self._connect() as conn:
            row = conn.execute(
                "select medops_llm_month_total(%s::date)",
                (month + "-01",),
            ).fetchone()
        return float(row[0]) if row else 0.0

    def reserve(self, month: str, cost_usd: float, cap_usd: float) -> SpendReservation | None:
        if cost_usd < 0 or cap_usd < 0:
            raise ValueError("cost and cap cannot be negative")
        reservation_id = str(uuid.uuid4())
        with self._connect() as conn:
            row = conn.execute(
                "select medops_llm_reserve(%s::date,%s::numeric,%s::numeric,%s::uuid)",
                (month + "-01", str(cost_usd), str(cap_usd), reservation_id),
            ).fetchone()
        if not row or not row[0]:
            return None
        return SpendReservation(reservation_id, month, cost_usd)

    def settle(self, reservation: SpendReservation, actual_usd: float) -> float:
        if actual_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._connect() as conn:
            row = conn.execute(
                "select medops_llm_settle(%s::uuid,%s::numeric)",
                (reservation.reservation_id, str(actual_usd)),
            ).fetchone()
        if not row:
            raise RuntimeError("spend settlement returned no total")
        return float(row[0])


def month_key(now: datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m")


class BudgetedGateway:
    """Reserve the call's worst case atomically, then settle the provider-reported cost.

    The optional run cap is a second, process-local bound for one explicitly authorized evaluation. It is checked
    before the shared monthly reservation. Failed provider calls consume their worst-case reservation in both
    ledgers, so an outage cannot silently leave room for more calls under the same authorization.
    """

    def __init__(
        self,
        inner: ModelGateway,
        *,
        prices: PriceTable,
        ledger: SpendLedger,
        monthly_cap_usd: float,
        run_cap_usd: float | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if monthly_cap_usd < 0 or (run_cap_usd is not None and run_cap_usd <= 0):
            raise ValueError("monthly cap cannot be negative and run cap must be positive")
        self._inner = inner
        self._prices = prices
        self._ledger = ledger
        self._cap = monthly_cap_usd
        self._run_cap = run_cap_usd
        self._run_spent = 0.0
        self._run_reserved = 0.0
        self._run_cap_blocked = False
        self._run_lock = threading.Lock()
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def provider(self) -> str:
        return self._inner.provider

    @property
    def monthly_cap_usd(self) -> float:
        return self._cap

    @property
    def run_cap_usd(self) -> float | None:
        return self._run_cap

    @property
    def run_accounted_cost_usd(self) -> float:
        with self._run_lock:
            return self._run_spent

    @property
    def run_cap_blocked(self) -> bool:
        with self._run_lock:
            return self._run_cap_blocked

    def _reserve_run(self, worst: float) -> None:
        with self._run_lock:
            if self._run_cap is not None and self._run_spent + self._run_reserved + worst > self._run_cap:
                self._run_cap_blocked = True
                raise BudgetExceeded(
                    f"run LLM cap {self._run_cap:.2f} USD would be exceeded: "
                    f"accounted {self._run_spent:.4f}, outstanding {self._run_reserved:.4f}, next call up to {worst:.4f}"
                )
            self._run_reserved += worst

    def _release_run(self, worst: float) -> None:
        with self._run_lock:
            self._run_reserved -= worst

    def _settle_run(self, worst: float, actual: float) -> None:
        with self._run_lock:
            self._run_reserved -= worst
            self._run_spent += actual

    def complete(self, request: ModelRequest) -> ModelResponse:
        month = month_key(self._clock())
        worst = self._prices.worst_case_usd(request)
        self._reserve_run(worst)
        try:
            reservation = self._ledger.reserve(month, worst, self._cap)
        except Exception:
            self._release_run(worst)
            raise
        if reservation is None:
            self._release_run(worst)
            spent = self._ledger.month_total(month)
            raise BudgetExceeded(
                f"monthly LLM cap {self._cap:.2f} USD would be exceeded: spent {spent:.4f}, next call up to {worst:.4f}"
            )
        try:
            response = self._inner.complete(request)
        except Exception:
            try:
                self._ledger.settle(reservation, reservation.reserved_usd)
            finally:
                self._settle_run(worst, reservation.reserved_usd)
            raise
        try:
            self._ledger.settle(reservation, response.cost_usd)
        finally:
            self._settle_run(worst, response.cost_usd)
        return response
