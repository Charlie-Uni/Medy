"""Per-request metering of gateway calls (INV-OBS-01: calls, tokens and cost per trace)."""

from __future__ import annotations

import threading

from medops.core.deadline import check_deadline, remaining_timeout
from medops.core.telemetry import annotate, span
from medops.infrastructure.llm.accounting import capture_call, new_call
from medops.infrastructure.llm.execution_budget import PRICES, complete_in_execution
from medops.infrastructure.llm.gateway import (
    ModelCallReceipt,
    ModelGateway,
    ModelOutputInvalid,
    ModelRequest,
    ModelResponse,
    PriceTable,
)


class MeteredGateway:
    def __init__(self, inner: ModelGateway) -> None:
        self._inner = inner
        self.calls = 0
        self.tokens = 0
        self.cost_usd = 0.0
        self.actual_cost_usd = 0.0
        self.conservative_cost_usd = 0.0
        self._receipts: dict[str, ModelCallReceipt] = {}
        self._lock = threading.Lock()

    @property
    def receipts(self) -> tuple[ModelCallReceipt, ...]:
        with self._lock:
            return tuple(self._receipts.values())

    def _record(self, receipt: ModelCallReceipt) -> None:
        with self._lock:
            prior = self._receipts.get(receipt.call.call_id)
            if prior is not None:
                if prior != receipt:
                    raise ValueError("model call already accounted with a different receipt")
                return
            self._receipts[receipt.call.call_id] = receipt
            self.calls += int(receipt.provider_started)
            self.tokens += receipt.usage.total_tokens if receipt.usage is not None else 0
            self.cost_usd += receipt.accounted_cost_usd
            self.actual_cost_usd += receipt.actual_cost_usd or 0
            if receipt.cost_basis in {"conservative_reservation", "reservation_uncertain"}:
                self.conservative_cost_usd += receipt.accounted_cost_usd

    @property
    def provider(self) -> str:
        return self._inner.provider

    @property
    def execution_prices(self) -> PriceTable:
        return getattr(self._inner, "execution_prices", PRICES)

    def complete(self, request: ModelRequest) -> ModelResponse:
        check_deadline()
        call = request.call or new_call(request, self.provider)
        request = request.model_copy(update={"timeout_s": remaining_timeout(request.timeout_s), "call": call})
        # the `gen_ai.*` names are the OpenTelemetry GenAI conventions, which trace viewers for model calls read
        # (model, token counts); still structure only — never the prompt or the reply (INV-OBS-03)
        with span(
            "llm.call",
            purpose=request.purpose,
            model_id=request.model_id,
            **{"gen_ai.operation.name": "chat", "gen_ai.request.model": request.model_id},
        ) as current:
            with capture_call(call.call_id) as capture:
                try:
                    response = complete_in_execution(
                        request, self._inner.complete, provider=self.provider, prices=self.execution_prices
                    )
                except BaseException as exc:
                    known = exc.model_response if isinstance(exc, ModelOutputInvalid) else None
                    receipt = capture.receipt or ModelCallReceipt(
                        call=call,
                        outcome="failed" if isinstance(exc, Exception) else "cancelled",
                        provider_started=True,
                        estimated_cost_usd=0,
                        actual_cost_usd=known.cost_usd if known else None,
                        accounted_cost_usd=known.cost_usd if known else 0,
                        cost_basis="reported_usage" if known else "unreported",
                        settlement_status="not_required",
                        usage=known.usage if known else None,
                        response_id=known.response_id if known else None,
                        response_model=known.model_id if known else None,
                        error_type=type(exc).__name__,
                    )
                    if receipt.call.call_id != call.call_id:
                        raise ValueError("model receipt belongs to a different call") from exc
                    self._record(receipt)
                    _annotate_receipt(current, receipt)
                    raise
                receipt = (
                    response.call_receipt
                    or capture.receipt
                    or ModelCallReceipt(
                        call=call,
                        outcome="succeeded",
                        provider_started=True,
                        estimated_cost_usd=0,
                        actual_cost_usd=response.cost_usd,
                        accounted_cost_usd=response.cost_usd,
                        cost_basis="reported_usage",
                        settlement_status="not_required",
                        usage=response.usage,
                        response_id=response.response_id,
                        response_model=response.model_id,
                    )
                )
                if receipt.call.call_id != call.call_id:
                    raise ValueError("model receipt belongs to a different call")
                self._record(receipt)
                _annotate_receipt(current, receipt)
                annotate(current, truncated=response.truncated)
                return response.model_copy(update={"call_receipt": receipt})


def _annotate_receipt(current, receipt: ModelCallReceipt) -> None:
    usage = receipt.usage
    annotate(
        current,
        call_id=receipt.call.call_id,
        reservation_id=receipt.call.reservation_id,
        run_id=receipt.call.run_id,
        attempt_id=receipt.call.attempt_id,
        call_outcome=receipt.outcome,
        provider_started=receipt.provider_started,
        cost_usd=receipt.accounted_cost_usd,
        accounted_cost_usd=receipt.accounted_cost_usd,
        actual_cost_usd=receipt.actual_cost_usd,
        estimated_cost_usd=receipt.estimated_cost_usd,
        cost_basis=receipt.cost_basis,
        settlement_status=receipt.settlement_status,
        error_type=receipt.error_type,
        settlement_error_type=receipt.settlement_error_type,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        **{
            "gen_ai.response.model": receipt.response_model,
            "gen_ai.usage.input_tokens": usage.input_tokens if usage else None,
            "gen_ai.usage.output_tokens": usage.output_tokens if usage else None,
            "gen_ai.usage.cost": receipt.actual_cost_usd,
        },
    )
