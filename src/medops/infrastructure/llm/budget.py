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
from psycopg.types.json import Jsonb

from medops.core.deadline import check_deadline, remaining_timeout
from medops.core.errors import ErrorCode, InfrastructureError
from medops.infrastructure.llm.accounting import new_call, publish_receipt
from medops.infrastructure.llm.execution_budget import (
    ExecutionBudgetExceeded,
    admitted_cost,
    complete_in_execution,
    current_budget,
)
from medops.infrastructure.llm.gateway import (
    BudgetExceeded,
    ModelCall,
    ModelCallReceipt,
    ModelGateway,
    ModelOutputInvalid,
    ModelRequest,
    ModelResponse,
    PriceTable,
)


@dataclass(frozen=True)
class SpendReservation:
    reservation_id: str
    month: str
    reserved_usd: float


class SpendLedger(Protocol):
    def month_total(self, month: str) -> float: ...

    def reserve(
        self, month: str, cost_usd: float, cap_usd: float, *, call: ModelCall | None = None
    ) -> SpendReservation | None: ...

    def settle(
        self, reservation: SpendReservation, actual_usd: float, *, receipt: ModelCallReceipt | None = None
    ) -> float: ...


class InMemorySpendLedger:
    """Thread-safe test ledger with the same reservation contract as PostgreSQL."""

    def __init__(self) -> None:
        self._totals: dict[str, float] = {}
        self._reserved: dict[str, float] = {}
        self._reservations: dict[str, tuple[str, float, float | None]] = {}
        self._calls: dict[str, ModelCall] = {}
        self._receipts: dict[str, ModelCallReceipt] = {}
        self._lock = threading.Lock()

    @property
    def receipts(self) -> tuple[ModelCallReceipt, ...]:
        with self._lock:
            return tuple(self._receipts.values())

    def month_total(self, month: str) -> float:
        with self._lock:
            return self._totals.get(month, 0.0)

    def reserve(
        self, month: str, cost_usd: float, cap_usd: float, *, call: ModelCall | None = None
    ) -> SpendReservation | None:
        if cost_usd < 0 or cap_usd < 0:
            raise ValueError("cost and cap cannot be negative")
        with self._lock:
            if self._totals.get(month, 0.0) + self._reserved.get(month, 0.0) + cost_usd > cap_usd:
                return None
            reservation_id = call.reservation_id if call and call.reservation_id else str(uuid.uuid4())
            if reservation_id in self._reservations:
                raise ValueError("spend reservation already exists")
            if call is not None:
                if call.reservation_id != reservation_id or any(
                    c.call_id == call.call_id for c in self._calls.values()
                ):
                    raise ValueError("missing reservation identity or duplicate model call")
                self._calls[reservation_id] = call
            self._reserved[month] = self._reserved.get(month, 0.0) + cost_usd
            self._reservations[reservation_id] = (month, cost_usd, None)
            return SpendReservation(reservation_id, month, cost_usd)

    def settle(
        self, reservation: SpendReservation, actual_usd: float, *, receipt: ModelCallReceipt | None = None
    ) -> float:
        if actual_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._lock:
            current = self._reservations.get(reservation.reservation_id)
            if current is None or current[:2] != (reservation.month, reservation.reserved_usd):
                raise ValueError("unknown or mismatched spend reservation")
            if receipt is not None:
                if (
                    receipt.call != self._calls.get(reservation.reservation_id)
                    or receipt.accounted_cost_usd != actual_usd
                    or receipt.settlement_status != "settled"
                ):
                    raise ValueError("receipt does not match spend reservation")
                prior = self._receipts.get(reservation.reservation_id)
                if prior is not None and prior != receipt:
                    raise ValueError("spend reservation already has a different receipt")
            if current[2] is not None:
                if current[2] != actual_usd:
                    raise ValueError("spend reservation already settled differently")
                if receipt is not None:
                    self._receipts[reservation.reservation_id] = receipt
                return self._totals.get(reservation.month, 0.0)
            self._reserved[reservation.month] -= reservation.reserved_usd
            self._totals[reservation.month] = self._totals.get(reservation.month, 0.0) + actual_usd
            self._reservations[reservation.reservation_id] = (*current[:2], actual_usd)
            if receipt is not None:
                self._receipts[reservation.reservation_id] = receipt
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

    def reserve(
        self, month: str, cost_usd: float, cap_usd: float, *, call: ModelCall | None = None
    ) -> SpendReservation | None:
        if cost_usd < 0 or cap_usd < 0:
            raise ValueError("cost and cap cannot be negative")
        reservation_id = call.reservation_id if call and call.reservation_id else str(uuid.uuid4())
        with self._connect() as conn:
            params = (month + "-01", str(cost_usd), str(cap_usd), reservation_id)
            if call is None:
                row = conn.execute(
                    "select medops_llm_reserve(%s::date,%s::numeric,%s::numeric,%s::uuid)", params
                ).fetchone()
            else:
                row = conn.execute(
                    "select medops_llm_reserve_call(%s::date,%s::numeric,%s::numeric,%s::uuid,%s::jsonb)",
                    (*params, Jsonb(call.model_dump(mode="json"))),
                ).fetchone()
        if not row or not row[0]:
            return None
        return SpendReservation(reservation_id, month, cost_usd)

    def settle(
        self, reservation: SpendReservation, actual_usd: float, *, receipt: ModelCallReceipt | None = None
    ) -> float:
        if actual_usd < 0:
            raise ValueError("cost cannot be negative")
        with self._connect() as conn:
            if receipt is None:
                row = conn.execute(
                    "select medops_llm_settle(%s::uuid,%s::numeric)",
                    (reservation.reservation_id, str(actual_usd)),
                ).fetchone()
            else:
                row = conn.execute(
                    "select medops_llm_settle_call(%s::uuid,%s::numeric,%s::jsonb)",
                    (reservation.reservation_id, str(actual_usd), Jsonb(receipt.model_dump(mode="json"))),
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
        require_execution_budget: bool = False,
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
        self._require_execution_budget = require_execution_budget

    @property
    def provider(self) -> str:
        return self._inner.provider

    @property
    def execution_prices(self) -> PriceTable:
        return self._prices

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

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            close()

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self._require_execution_budget and current_budget() is None:
            call = request.call or new_call(request, self.provider)
            publish_receipt(
                ModelCallReceipt(
                    call=call,
                    outcome="denied",
                    provider_started=False,
                    estimated_cost_usd=0,
                    actual_cost_usd=0,
                    accounted_cost_usd=0,
                    cost_basis="not_started",
                    settlement_status="not_required",
                    error_type="ExecutionBudgetExceeded",
                )
            )
            raise ExecutionBudgetExceeded("context")
        return complete_in_execution(request, self._complete, provider=self.provider, prices=self._prices)

    def _complete(self, request: ModelRequest) -> ModelResponse:
        call = (request.call or new_call(request, self.provider)).model_copy(
            update={"reservation_id": str(uuid.uuid4())}
        )
        request = request.model_copy(update={"call": call})
        month = month_key(self._clock())
        worst = 0.0
        try:
            check_deadline()
            request = request.model_copy(update={"timeout_s": remaining_timeout(request.timeout_s)})
            worst = self._prices.worst_case_usd(request)
            reserved = admitted_cost(call.call_id)
            if reserved is not None:
                worst = max(worst, reserved)
            self._reserve_run(worst)
        except BaseException as exc:
            publish_receipt(
                ModelCallReceipt(
                    call=call,
                    outcome="denied" if isinstance(exc, BudgetExceeded) else "failed",
                    provider_started=False,
                    estimated_cost_usd=worst,
                    actual_cost_usd=0,
                    accounted_cost_usd=0,
                    cost_basis="not_started",
                    settlement_status="not_required",
                    error_type=type(exc).__name__,
                )
            )
            raise
        try:
            reservation = self._ledger.reserve(month, worst, self._cap, call=call)
        except BaseException as exc:
            # A connection may fail after COMMIT. Keep the bound and the known reservation ID for reconciliation.
            self._settle_run(worst, worst)
            publish_receipt(
                ModelCallReceipt(
                    call=call,
                    outcome="failed" if isinstance(exc, Exception) else "cancelled",
                    provider_started=False,
                    estimated_cost_usd=worst,
                    actual_cost_usd=0,
                    accounted_cost_usd=worst,
                    cost_basis="reservation_uncertain",
                    settlement_status="pending",
                    error_type=type(exc).__name__,
                )
            )
            raise
        if reservation is None:
            self._release_run(worst)
            publish_receipt(
                ModelCallReceipt(
                    call=call,
                    outcome="denied",
                    provider_started=False,
                    estimated_cost_usd=worst,
                    actual_cost_usd=0,
                    accounted_cost_usd=0,
                    cost_basis="not_started",
                    settlement_status="not_required",
                    error_type="BudgetExceeded",
                )
            )
            raise BudgetExceeded(f"monthly LLM cap {self._cap:.2f} USD would be exceeded: next call up to {worst:.4f}")
        provider_started = False
        try:
            check_deadline()  # reservation may have waited for the ledger; do not start a late call
            provider_started = True
            response = self._inner.complete(request)
        except BaseException as exc:
            known = exc.model_response if isinstance(exc, ModelOutputInvalid) else None
            cost = known.cost_usd if known is not None else reservation.reserved_usd if provider_started else 0.0
            receipt = ModelCallReceipt(
                call=call,
                outcome="failed" if isinstance(exc, Exception) else "cancelled",
                provider_started=provider_started,
                estimated_cost_usd=worst,
                actual_cost_usd=known.cost_usd if known is not None else None if provider_started else 0,
                accounted_cost_usd=cost,
                cost_basis="reported_usage"
                if known is not None
                else "conservative_reservation"
                if provider_started
                else "not_started",
                settlement_status="settled",
                usage=known.usage if known else None,
                response_id=known.response_id if known else None,
                response_model=known.model_id if known else None,
                error_type=type(exc).__name__,
            )
            try:
                self._settle_call(reservation, worst, receipt)
            except Exception as settlement_error:
                if not isinstance(exc, Exception):
                    # Cancellation must still stop the enclosing task even when accounting is unavailable.
                    raise exc from settlement_error
                raise
            raise
        receipt = ModelCallReceipt(
            call=call,
            outcome="succeeded",
            provider_started=True,
            estimated_cost_usd=worst,
            actual_cost_usd=response.cost_usd,
            accounted_cost_usd=response.cost_usd,
            cost_basis="reported_usage",
            settlement_status="settled",
            usage=response.usage,
            response_id=response.response_id,
            response_model=response.model_id,
        )
        self._settle_call(reservation, worst, receipt)
        return response.model_copy(update={"call_receipt": receipt})

    def _settle_call(self, reservation: SpendReservation, worst: float, receipt: ModelCallReceipt) -> None:
        try:
            self._ledger.settle(reservation, receipt.accounted_cost_usd, receipt=receipt)
        except BaseException as exc:
            publish_receipt(
                receipt.model_copy(update={"settlement_status": "pending", "settlement_error_type": type(exc).__name__})
            )
            if not isinstance(exc, Exception):
                raise
            raise InfrastructureError(
                ErrorCode.audit_unavailable, detail="LLM settlement requires reconciliation", retryable=False
            ) from exc
        else:
            publish_receipt(receipt)
        finally:
            self._settle_run(worst, receipt.accounted_cost_usd)
