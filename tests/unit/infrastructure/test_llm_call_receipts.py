"""Call accounting must remain local when shared provider calls finish in a different order."""

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from medops.core.deadline import DeadlineExceeded, deadline_scope
from medops.core.errors import ErrorCode, InfrastructureError
from medops.core.tracing import bind_trace_id
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.budget import BudgetedGateway, InMemorySpendLedger
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import (
    OPENAI_PRICES,
    BudgetExceeded,
    ModelCall,
    ModelCallReceipt,
    ModelOutputInvalid,
    ModelTimeout,
    PriceTable,
)
from medops.infrastructure.llm.meter import MeteredGateway
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway
from tests.support.model_gateway import _completion, _FixedCost, _StubClient, req


def test_failed_request_does_not_charge_an_interleaved_success():
    entered, release = Event(), Event()
    prices = PriceTable(OPENAI_PRICES)
    failed_request = req(purpose="blocked_failure")
    worst = prices.worst_case_usd(failed_request)

    class InterleavedProvider(_FixedCost):
        def complete(self, request):
            if request.purpose == "blocked_failure":
                entered.set()
                assert release.wait(5), "test failed to release provider"
                raise ModelTimeout()
            return super().complete(request)

    shared = BudgetedGateway(
        InterleavedProvider(worst / 2), prices=prices, ledger=InMemorySpendLedger(), monthly_cap_usd=10
    )
    failed, succeeded = MeteredGateway(shared), MeteredGateway(shared)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(failed.complete, failed_request)
        try:
            assert entered.wait(5)
            succeeded.complete(req())
        finally:
            release.set()
        with pytest.raises(ModelTimeout):
            pending.result(timeout=5)
    assert failed.cost_usd == pytest.approx(worst)
    assert succeeded.cost_usd == pytest.approx(worst / 2)
    assert shared.run_accounted_cost_usd == pytest.approx(failed.cost_usd + succeeded.cost_usd)


def metered(inner, *, ledger=None, run_cap=None, monthly_cap=10):
    ledger = ledger or InMemorySpendLedger()
    budgeted = BudgetedGateway(
        inner, prices=PriceTable(OPENAI_PRICES), ledger=ledger, monthly_cap_usd=monthly_cap, run_cap_usd=run_cap
    )
    return MeteredGateway(budgeted), budgeted, ledger


def test_two_failures_keep_their_own_conservative_cost_even_with_the_same_exception():
    entered, release = Event(), Event()
    shared_error = ModelTimeout()

    class Provider:
        provider = "stub"

        def complete(self, request):
            if request.purpose == "first":
                entered.set()
                assert release.wait(5)
            raise shared_error

    first, gateway, ledger = metered(Provider())
    second = MeteredGateway(gateway)
    first_req, second_req = req(purpose="first"), req(purpose="second", text="x" * 400)
    prices = PriceTable(OPENAI_PRICES)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(first.complete, first_req)
        try:
            assert entered.wait(5)
            with pytest.raises(ModelTimeout):
                second.complete(second_req)
        finally:
            release.set()
        with pytest.raises(ModelTimeout):
            pending.result(timeout=5)
    assert first.cost_usd == pytest.approx(prices.worst_case_usd(first_req))
    assert second.cost_usd == pytest.approx(prices.worst_case_usd(second_req))
    assert first.receipts[0].call.call_id != second.receipts[0].call.call_id
    assert len(ledger.receipts) == 2
    assert not hasattr(shared_error, "call_receipt")  # shared exception objects cannot carry request state


def test_denied_monthly_reservation_does_not_count_another_requests_success():
    entered, release = Event(), Event()

    class Ledger(InMemorySpendLedger):
        def reserve(self, *args, call=None):
            if call and call.purpose == "denied":
                entered.set()
                assert release.wait(5)
                return None
            return super().reserve(*args, call=call)

    denied, shared, _ = metered(_FixedCost(0.00001), ledger=Ledger())
    succeeded = MeteredGateway(shared)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(denied.complete, req(purpose="denied"))
        try:
            assert entered.wait(5)
            succeeded.complete(req())
        finally:
            release.set()
        with pytest.raises(BudgetExceeded):
            pending.result(timeout=5)
    assert (denied.calls, denied.tokens, denied.cost_usd) == (0, 0, 0)
    receipt = denied.receipts[0]
    assert receipt.outcome == "denied" and not receipt.provider_started
    assert receipt.actual_cost_usd == 0 and receipt.settlement_status == "not_required"


def test_run_cap_denial_keeps_a_zero_cost_receipt_without_a_provider_call():
    inner = _FixedCost(0.00001)
    meter, gateway, _ = metered(inner, run_cap=0.000001)
    with pytest.raises(BudgetExceeded):
        meter.complete(req())
    assert inner.calls == 0 and meter.calls == 0 and gateway.run_cap_blocked
    assert meter.receipts[0].accounted_cost_usd == 0


@pytest.mark.parametrize("commit_first", [False, True])
def test_success_with_settlement_failure_keeps_known_usage_and_never_retries_provider(commit_first):
    class Ledger(InMemorySpendLedger):
        def settle(self, reservation, actual_usd, *, receipt=None):
            if commit_first:
                super().settle(reservation, actual_usd, receipt=receipt)
            raise OSError("private database connection information")

    inner = _FixedCost(0.00001)
    meter, gateway, ledger = metered(inner, ledger=Ledger())
    with pytest.raises(InfrastructureError) as error:
        meter.complete(req())
    assert error.value.code == ErrorCode.audit_unavailable and not error.value.retryable
    receipt = meter.receipts[0]
    assert receipt.outcome == "succeeded" and receipt.settlement_status == "pending"
    assert receipt.settlement_error_type == "OSError" and receipt.actual_cost_usd == 0.00001
    assert (meter.calls, meter.tokens, meter.actual_cost_usd, meter.conservative_cost_usd) == (1, 15, 0.00001, 0)
    assert gateway.run_accounted_cost_usd == meter.cost_usd == 0.00001 and inner.calls == 1
    assert "private database" not in receipt.model_dump_json()
    assert len(ledger.receipts) == int(commit_first)


def test_provider_failure_and_settlement_failure_keep_this_calls_estimate():
    class Ledger(InMemorySpendLedger):
        def settle(self, *args, **kwargs):
            raise OSError("not recorded")

    meter, gateway, _ = metered(FakeModelGateway({"answer": [ModelTimeout()]}), ledger=Ledger())
    with pytest.raises(InfrastructureError):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert receipt.error_type == "ModelTimeout" and receipt.settlement_error_type == "OSError"
    assert receipt.actual_cost_usd is None and receipt.usage is None
    assert receipt.cost_basis == "conservative_reservation" and receipt.settlement_status == "pending"
    assert meter.cost_usd == gateway.run_accounted_cost_usd == receipt.estimated_cost_usd
    assert meter.actual_cost_usd == 0 and meter.conservative_cost_usd == meter.cost_usd


@pytest.mark.parametrize("content,finish", [("not JSON", "stop"), ("[]", "stop"), ('{"a":', "length")])
def test_invalid_structured_reply_is_billed_from_its_reported_usage(content, finish):
    adapter = OpenAIModelGateway(_StubClient(_completion(content, finish=finish)))
    meter, _, ledger = metered(adapter)
    with pytest.raises(ModelOutputInvalid):
        meter.complete(req(schema={"type": "object"}))
    receipt = meter.receipts[0]
    assert receipt.actual_cost_usd == pytest.approx((120 * 0.10 + 30 * 0.50) / 1_000_000)
    assert receipt.cost_basis == "reported_usage" and receipt.response_id == "chatcmpl-1"
    assert meter.tokens == 150 and meter.conservative_cost_usd == 0
    assert ledger.receipts == meter.receipts


def test_cancellation_is_accounted_before_the_original_cancellation_propagates():
    meter, gateway, ledger = metered(FakeModelGateway({"answer": [asyncio.CancelledError()]}))
    with pytest.raises(asyncio.CancelledError):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert receipt.outcome == "cancelled" and receipt.settlement_status == "settled"
    assert receipt.actual_cost_usd is None and meter.calls == 1
    assert meter.cost_usd == gateway.run_accounted_cost_usd == receipt.estimated_cost_usd
    assert ledger.receipts == meter.receipts


def test_expiry_while_reserving_has_zero_usage_and_does_not_start_provider():
    class Ledger(InMemorySpendLedger):
        def reserve(self, *args, **kwargs):
            reservation = super().reserve(*args, **kwargs)
            time.sleep(0.02)
            return reservation

    inner = _FixedCost(0.00001)
    meter, gateway, ledger = metered(inner, ledger=Ledger())
    with deadline_scope(0.01), pytest.raises(DeadlineExceeded):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert not receipt.provider_started and receipt.actual_cost_usd == receipt.accounted_cost_usd == 0
    assert meter.calls == inner.calls == gateway.run_accounted_cost_usd == 0
    assert ledger.receipts == meter.receipts


def test_uncertain_reservation_commit_keeps_identity_and_capacity_without_claiming_usage():
    class Ledger(InMemorySpendLedger):
        def reserve(self, *args, **kwargs):
            super().reserve(*args, **kwargs)
            raise OSError("commit acknowledgement lost")

    inner = _FixedCost(0.00001)
    worst = PriceTable(OPENAI_PRICES).worst_case_usd(req())
    meter, gateway, ledger = metered(inner, ledger=Ledger(), run_cap=worst)
    with pytest.raises(OSError):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert receipt.call.reservation_id in ledger._reservations
    assert receipt.cost_basis == "reservation_uncertain" and receipt.settlement_status == "pending"
    assert receipt.actual_cost_usd == 0 and receipt.accounted_cost_usd == worst
    with pytest.raises(BudgetExceeded):
        meter.complete(req())
    assert inner.calls == meter.calls == 0 and gateway.run_accounted_cost_usd == worst


def test_shared_request_meter_is_thread_safe_and_receipts_are_idempotent():
    meter, _, ledger = metered(_FixedCost(0.00001))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: meter.complete(req()), range(64)))
    assert meter.calls == 64 and meter.tokens == 64 * 15
    assert meter.cost_usd == pytest.approx(64 * 0.00001)
    assert len({r.call.call_id for r in meter.receipts}) == len(ledger.receipts) == 64
    original = meter.receipts[0]
    meter._record(original)
    assert meter.calls == 64
    with pytest.raises(ValueError, match="different receipt"):
        meter._record(original.model_copy(update={"actual_cost_usd": 0.9}))


def test_receipt_ownership_survives_nested_scope_and_copied_translation_context():
    from contextvars import copy_context

    meter, _, _ = metered(_FixedCost(0.00001))
    trace_id = "a" * 32
    with bind_trace_id(trace_id), call_scope(run_id="replay-run", attempt_id="task:1"):
        with call_scope(attempt_id="retrieval-key:2"):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(copy_context().run, meter.complete, req(purpose="query_translation")).result(timeout=5)
        meter.complete(req())
    first, second = meter.receipts
    assert first.call.trace_id == second.call.trace_id == trace_id
    assert first.call.run_id == second.call.run_id == "replay-run"
    assert first.call.attempt_id == "task:1/retrieval-key:2"
    assert second.call.attempt_id == "task:1"
    assert first.call.reservation_id != second.call.reservation_id


def test_cancellation_survives_a_settlement_failure_and_keeps_pending_receipt():
    class Ledger(InMemorySpendLedger):
        def settle(self, *args, **kwargs):
            raise OSError("settlement connection lost")

    meter, gateway, _ = metered(FakeModelGateway({"answer": [asyncio.CancelledError()]}), ledger=Ledger())
    with pytest.raises(asyncio.CancelledError):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert receipt.outcome == "cancelled" and receipt.settlement_status == "pending"
    assert receipt.error_type == "CancelledError" and receipt.settlement_error_type == "OSError"
    assert meter.calls == 1 and meter.cost_usd == gateway.run_accounted_cost_usd


def test_cancellation_during_settlement_keeps_known_usage_and_original_signal():
    class Ledger(InMemorySpendLedger):
        def settle(self, *args, **kwargs):
            raise asyncio.CancelledError()

    meter, gateway, _ = metered(_FixedCost(0.00001), ledger=Ledger())
    with pytest.raises(asyncio.CancelledError):
        meter.complete(req())
    receipt = meter.receipts[0]
    assert receipt.outcome == "succeeded" and receipt.settlement_status == "pending"
    assert receipt.settlement_error_type == "CancelledError" and meter.actual_cost_usd == 0.00001
    assert meter.cost_usd == gateway.run_accounted_cost_usd


def test_in_memory_ledger_rejects_duplicate_call_and_attaches_receipt_after_legacy_settlement():
    ledger = InMemorySpendLedger()
    call = ModelCall(
        call_id=str(uuid.uuid4()),
        reservation_id=str(uuid.uuid4()),
        purpose="answer",
        requested_model="stub",
        provider="stub",
    )
    reservation = ledger.reserve("2099-01", 0.1, 1, call=call)
    assert reservation is not None
    with pytest.raises(ValueError, match="duplicate model call"):
        ledger.reserve("2099-01", 0.1, 1, call=call.model_copy(update={"reservation_id": str(uuid.uuid4())}))
    receipt = ModelCallReceipt(
        call=call,
        outcome="succeeded",
        provider_started=True,
        estimated_cost_usd=0.1,
        actual_cost_usd=0.05,
        accounted_cost_usd=0.05,
        cost_basis="reported_usage",
        settlement_status="settled",
    )
    ledger.settle(reservation, 0.05)
    ledger.settle(reservation, 0.05, receipt=receipt)
    assert ledger.receipts == (receipt,)
    assert ledger.month_total("2099-01") == 0.05


def test_nested_meters_propagate_one_receipt_for_a_failed_call():
    meter, _, _ = metered(FakeModelGateway({"answer": [ModelTimeout()]}))
    outer = MeteredGateway(meter)
    with pytest.raises(ModelTimeout):
        outer.complete(req())
    assert outer.receipts == meter.receipts and outer.cost_usd == meter.cost_usd


def test_provider_cannot_attach_another_calls_receipt():
    other, _, _ = metered(_FixedCost(0.00001))
    response = other.complete(req())

    class Provider:
        provider = "stub"

        def complete(self, request):
            return response

    meter = MeteredGateway(Provider())
    with pytest.raises(ValueError, match="different call"):
        meter.complete(req())
    assert not meter.receipts and meter.cost_usd == 0


def test_node_retries_have_distinct_call_ids_and_join_to_their_attempts():
    from medops.harness.contracts import NodeSpec, run_node

    meter, gateway, ledger = metered(FakeModelGateway({"answer": [ModelTimeout(), {"ok": True}]}))
    key, trace_id = "b" * 64, "a" * 32
    with bind_trace_id(trace_id), call_scope(run_id="replay-run"):
        _, attempts = run_node(
            NodeSpec(name="answer", timeout_s=1), key, lambda: meter.complete(req()), sleep=lambda _: None
        )
    assert [a.outcome for a in attempts] == ["retry", "ok"]
    assert [r.call.attempt_id for r in meter.receipts] == [f"{key}:1", f"{key}:2"]
    assert len({r.call.call_id for r in meter.receipts}) == len({r.call.reservation_id for r in meter.receipts}) == 2
    assert all(r.call.trace_id == trace_id and r.call.run_id == "replay-run" for r in meter.receipts)
    assert meter.cost_usd == gateway.run_accounted_cost_usd and ledger.receipts == meter.receipts


def test_real_harness_propagates_run_and_operation_identity_to_answer_receipt():
    from medops.harness.dependencies import HarnessDeps
    from medops.harness.runtime import initial_state, run_ask
    from tests.support.harness import LABEL, FakeRetrieval, fast_specs
    from tests.support.harness_data import evidence, user, versions

    reply = {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}
    meter, _, _ = metered(FakeModelGateway({"answer": [reply]}))
    state = initial_state(
        user=user(), query="拔痛酸錠用於6至12歲兒童時口服劑量如何給予？", versions=versions(), run_id="replay-run"
    )
    deps = HarnessDeps(
        retrieval=FakeRetrieval(evidence("c1", LABEL)), gateway=meter, answer_model_id="gpt-6-sol", specs=fast_specs()
    )
    run = run_ask(state, deps)
    assert run.outcome == "answered"
    answer_attempt = next(a for a in run.attempts if a.node == "answer")
    receipt = meter.receipts[0]
    assert receipt.call.trace_id == state.trace_id and receipt.call.run_id == state.run_id
    assert receipt.call.attempt_id == f"{answer_attempt.operation_key}:{answer_attempt.attempt}"


def test_failed_call_telemetry_distinguishes_estimate_and_keeps_content_out():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    from medops.core import telemetry

    exp = InMemorySpanExporter()
    telemetry.install_exporter(exp, batch=False)
    meter, _, _ = metered(FakeModelGateway({"answer": [ModelTimeout("private failure content")]}))
    try:
        with bind_trace_id(), pytest.raises(ModelTimeout):
            meter.complete(req(text="private prompt content"))
        current = next(s for s in exp.get_finished_spans() if s.name == "llm.call")
        attrs = dict(current.attributes)
        receipt = meter.receipts[0]
        assert attrs["call_id"] == receipt.call.call_id and attrs["reservation_id"] == receipt.call.reservation_id
        assert attrs["cost_basis"] == "conservative_reservation" and attrs["settlement_status"] == "settled"
        assert "gen_ai.usage.cost" not in attrs and "input_tokens" not in attrs
        assert attrs["accounted_cost_usd"] == receipt.accounted_cost_usd
        assert not current.events
        blob = str(attrs) + receipt.model_dump_json()
        assert "private failure content" not in blob and "private prompt content" not in blob
    finally:
        telemetry.set_tracer_provider(None)
