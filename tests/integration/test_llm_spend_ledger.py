"""The runtime budget is shared across processes and reserves capacity before provider calls."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg import errors

from medops.infrastructure.llm.budget import PostgresSpendLedger


def test_postgres_ledger_is_durable_atomic_and_settlement_is_idempotent(migrated):
    month = "2099-01"
    first = PostgresSpendLedger(migrated)
    second = PostgresSpendLedger(migrated)
    reservation = first.reserve(month, 0.6, 1.0)
    assert reservation is not None
    assert second.reserve(month, 0.5, 1.0) is None
    assert first.settle(reservation, 0.4) == 0.4
    assert first.settle(reservation, 0.4) == 0.4
    assert second.reserve(month, 0.6, 1.0) is not None


def test_database_rejects_unknown_settlement(migrated):
    with psycopg.connect(migrated) as conn:
        try:
            conn.execute("select medops_llm_settle(%s::uuid,0.1)", (str(uuid.uuid4()),))
        except psycopg.Error:
            pass
        else:
            raise AssertionError("unknown reservation was accepted")


def test_app_role_can_use_budget_functions_without_reading_ledger_tables(login_users):
    app_dsn = login_users["app"]["dsn"]
    ledger = PostgresSpendLedger(app_dsn)
    month = "2098-02"

    assert ledger.month_total(month) == 0.0
    reservation = ledger.reserve(month, 0.6, 1.0)
    assert reservation is not None
    assert ledger.settle(reservation, 0.4) == 0.4
    assert ledger.month_total(month) == 0.4

    with psycopg.connect(app_dsn) as conn, pytest.raises(errors.InsufficientPrivilege):
        conn.execute("select * from llm_monthly_spend")
