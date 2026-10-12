"""Call receipts are durable, atomic with settlement and restricted to accounting metadata."""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import psycopg
import pytest
from psycopg import errors
from psycopg.types.json import Jsonb

from medops.core.tracing import bind_trace_id
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.budget import BudgetedGateway, PostgresSpendLedger
from medops.infrastructure.llm.execution_budget import default_limits, execution_scope, request_tokens
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import OPENAI_PRICES, ModelCall, ModelCallReceipt, ModelTimeout, PriceTable
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.database import run_alembic
from tests.support.model_gateway import _FixedCost, req


def call_identity():
    return ModelCall(
        call_id=str(uuid.uuid4()),
        trace_id=uuid.uuid4().hex,
        run_id="run-test",
        attempt_id="node:1",
        reservation_id=str(uuid.uuid4()),
        purpose="answer",
        requested_model="gpt-6-luna",
        provider="stub",
    )


def receipt_for(call):
    return ModelCallReceipt(
        call=call,
        outcome="succeeded",
        provider_started=True,
        estimated_cost_usd=0.1,
        actual_cost_usd=0.05,
        accounted_cost_usd=0.05,
        cost_basis="reported_usage",
        settlement_status="settled",
    )


def test_parallel_requests_persist_their_own_receipts_with_app_role(login_users, migrated):
    ledger = PostgresSpendLedger(login_users["app"]["dsn"])
    shared = BudgetedGateway(
        FakeModelGateway({"answer": [ModelTimeout()]}),
        prices=PriceTable(OPENAI_PRICES),
        ledger=ledger,
        monthly_cap_usd=10,
        clock=lambda: datetime(2097, 1, 1, tzinfo=UTC),
    )
    success_gateway = BudgetedGateway(
        _FixedCost(0.00001),
        prices=PriceTable(OPENAI_PRICES),
        ledger=ledger,
        monthly_cap_usd=10,
        clock=lambda: datetime(2097, 1, 1, tzinfo=UTC),
    )

    def execute(gateway, fail):
        meter = MeteredGateway(gateway)
        with bind_trace_id(), call_scope(run_id="receipt-test", attempt_id="retrieval-key:1"):
            if fail:
                with pytest.raises(ModelTimeout):
                    meter.complete(req(text="x" * 400))
            else:
                meter.complete(req())
        return meter

    with ThreadPoolExecutor(max_workers=2) as pool:
        failed = pool.submit(execute, shared, True)
        succeeded = pool.submit(execute, success_gateway, False)
        meters = [failed.result(timeout=10), succeeded.result(timeout=10)]
    with psycopg.connect(migrated) as conn:
        for meter in meters:
            receipt = meter.receipts[0]
            row = conn.execute(
                "select call_context, call_receipt, actual_usd from llm_spend_reservations where reservation_id=%s::uuid",
                (receipt.call.reservation_id,),
            ).fetchone()
            assert row[0] == receipt.call.model_dump(mode="json")
            assert row[1] == receipt.model_dump(mode="json")
            assert float(row[2]) == pytest.approx(receipt.accounted_cost_usd, abs=0.0000005)
            assert receipt.call.run_id == "receipt-test" and receipt.call.attempt_id == "retrieval-key:1"
    assert meters[0].receipts[0].actual_cost_usd is None and meters[0].tokens == 0
    assert meters[1].actual_cost_usd == 0.00001 and meters[1].tokens == 15
    assert ledger.month_total("2097-01") == pytest.approx(sum(m.cost_usd for m in meters), abs=0.000001)


def test_duplicate_and_changed_receipts_are_atomic_and_idempotent(migrated):
    ledger = PostgresSpendLedger(migrated)
    call = call_identity()
    reservation = ledger.reserve("2097-02", 0.1, 1, call=call)
    assert reservation is not None
    receipt = receipt_for(call)
    assert ledger.settle(reservation, 0.05, receipt=receipt) == 0.05
    assert ledger.settle(reservation, 0.05, receipt=receipt) == 0.05
    with pytest.raises(errors.RestrictViolation):
        ledger.settle(reservation, 0.05, receipt=receipt.model_copy(update={"response_id": "another"}))
    with pytest.raises(errors.CheckViolation):
        ledger.settle(reservation, 0.06, receipt=receipt)
    with pytest.raises(errors.CheckViolation):
        ledger.settle(reservation, 0.05, receipt=receipt.model_copy(update={"call": call_identity()}))
    with pytest.raises(errors.UniqueViolation):
        ledger.reserve("2097-02", 0.1, 1, call=call.model_copy(update={"reservation_id": str(uuid.uuid4())}))
    with psycopg.connect(migrated) as conn:
        spent, reserved = conn.execute(
            "select spent_usd,reserved_usd from llm_monthly_spend where month='2097-02-01'"
        ).fetchone()
        assert float(spent) == 0.05 and float(reserved) == 0


def test_execution_reservation_and_known_usage_agree_with_durable_call_receipts(login_users, migrated):
    ledger = PostgresSpendLedger(login_users["app"]["dsn"])
    meter = MeteredGateway(
        BudgetedGateway(
            FakeModelGateway({"answer": [ModelTimeout()]}),
            prices=PriceTable(OPENAI_PRICES),
            ledger=ledger,
            monthly_cap_usd=10,
            clock=lambda: datetime(2097, 6, 1, tzinfo=UTC),
            require_execution_budget=True,
        )
    )
    request = req(text="繁體字" * 100, schema={"type": "object", "properties": {"result": {"type": "string"}}})
    with execution_scope(default_limits(timeout_s=10)) as budget, pytest.raises(ModelTimeout):
        meter.complete(request)
    snapshot = budget.snapshot()
    receipt = meter.receipts[0]
    assert snapshot.accounted_tokens == request_tokens(request) and snapshot.known_tokens == 0
    assert snapshot.accounted_cost_usd == receipt.accounted_cost_usd == receipt.estimated_cost_usd
    with psycopg.connect(migrated) as conn:
        row = conn.execute(
            "select reserved_usd,call_receipt from llm_spend_reservations where reservation_id=%s::uuid",
            (receipt.call.reservation_id,),
        ).fetchone()
        assert float(row[0]) == pytest.approx(snapshot.accounted_cost_usd, abs=0.0000005)
        assert row[1] == receipt.model_dump(mode="json")
    assert ledger.month_total("2097-06") == pytest.approx(snapshot.accounted_cost_usd, abs=0.0000005)


@pytest.mark.parametrize("location", ["context", "receipt", "usage", "nested_scalar"])
def test_database_rejects_body_fields_without_altering_budget(migrated, location):
    call = call_identity()
    context = call.model_dump(mode="json")
    receipt = receipt_for(call).model_dump(mode="json")
    if location == "context":
        context["prompt"] = "private prompt"
    elif location == "receipt":
        receipt["text"] = "private reply"
    elif location == "usage":
        receipt["usage"] = {"input_tokens": 1, "text": "private reply"}
    else:
        receipt["error_type"] = {"text": "private exception"}
    with psycopg.connect(migrated) as conn:
        if location == "context":
            with pytest.raises(errors.CheckViolation):
                conn.execute(
                    "select medops_llm_reserve_call('2097-03-01',0.1,1,%s::uuid,%s::jsonb)",
                    (call.reservation_id, Jsonb(context)),
                )
        else:
            conn.execute(
                "select medops_llm_reserve_call('2097-03-01',0.1,1,%s::uuid,%s::jsonb)",
                (call.reservation_id, Jsonb(context)),
            )
            conn.commit()
            with pytest.raises(errors.CheckViolation):
                conn.execute(
                    "select medops_llm_settle_call(%s::uuid,0.05,%s::jsonb)",
                    (call.reservation_id, Jsonb(receipt)),
                )
            conn.rollback()
            assert conn.execute(
                "select call_receipt,settled_at from llm_spend_reservations where reservation_id=%s::uuid",
                (call.reservation_id,),
            ).fetchone() == (None, None)


def test_app_cannot_read_or_update_receipts_and_readonly_cannot_call_functions(login_users):
    for statement in ["select * from llm_spend_reservations", "update llm_spend_reservations set call_receipt='{}'"]:
        with psycopg.connect(login_users["app"]["dsn"]) as conn, pytest.raises(errors.InsufficientPrivilege):
            conn.execute(statement)
    with psycopg.connect(login_users["readonly"]["dsn"]) as conn, pytest.raises(errors.InsufficientPrivilege):
        conn.execute("select medops_llm_reserve_call('2097-01-01',0.1,1,%s::uuid,'{}')", (str(uuid.uuid4()),))


@pytest.mark.parametrize("legacy_first", [False, True])
def test_idempotent_receipts_preserve_submicro_precision(migrated, legacy_first):
    call = call_identity()
    ledger = PostgresSpendLedger(migrated)
    reservation = ledger.reserve("2097-05", 0.1, 1, call=call)
    assert reservation is not None
    receipt = receipt_for(call).model_copy(update={"actual_cost_usd": 0.0000502, "accounted_cost_usd": 0.0000502})
    if legacy_first:
        ledger.settle(reservation, 0.0000502)
    ledger.settle(reservation, 0.0000502, receipt=receipt)
    before = ledger.month_total("2097-05")
    ledger.settle(reservation, 0.0000502, receipt=receipt)
    assert ledger.month_total("2097-05") == before
    with psycopg.connect(migrated) as conn:
        row = conn.execute(
            "select actual_usd,call_receipt from llm_spend_reservations where reservation_id=%s::uuid",
            (reservation.reservation_id,),
        ).fetchone()
        assert float(row[0]) == 0.00005 and row[1]["actual_cost_usd"] == 0.0000502


def test_0023_round_trip_keeps_legacy_spend_and_reservations(scratch_database):
    run_alembic(scratch_database, "upgrade", "0022")
    ledger = PostgresSpendLedger(scratch_database)
    reservation = ledger.reserve("2097-04", 0.1, 1)
    assert reservation is not None
    ledger.settle(reservation, 0.05)
    run_alembic(scratch_database, "upgrade", "0023")
    call = call_identity()
    new = ledger.reserve("2097-04", 0.1, 1, call=call)
    assert new is not None
    ledger.settle(new, 0.05, receipt=receipt_for(call))
    run_alembic(scratch_database, "downgrade", "0022")
    assert ledger.month_total("2097-04") == 0.1
    run_alembic(scratch_database, "upgrade", "0023")
    with psycopg.connect(scratch_database) as conn:
        rows = conn.execute("select actual_usd,call_context,call_receipt from llm_spend_reservations").fetchall()
        assert len(rows) == 2
        assert all(float(row[0]) == 0.05 and row[1] == {} and row[2] is None for row in rows)
