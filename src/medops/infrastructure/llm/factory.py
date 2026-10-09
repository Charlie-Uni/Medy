"""Shared gateway assembly; callers own the lifetime of the gateway and its meters."""

from __future__ import annotations

from medops.core.config import Settings
from medops.infrastructure.llm.budget import BudgetedGateway, PostgresSpendLedger, SpendLedger
from medops.infrastructure.llm.gateway import OPENAI_PRICES, PriceTable
from medops.infrastructure.llm.openai_gateway import OpenAIModelGateway


def build_budgeted_gateway(
    settings: Settings, *, ledger: SpendLedger | None = None, run_cap_usd: float | None = None
) -> BudgetedGateway:
    """Create a gateway against the shared durable monthly ledger (or an explicit test ledger)."""
    durable = ledger or PostgresSpendLedger(
        settings.database_url.get_secret_value(),
        connect_timeout_s=settings.db_connect_timeout_s,
        statement_timeout_ms=min(settings.db_statement_timeout_ms, 5000),
    )
    return BudgetedGateway(
        OpenAIModelGateway.from_settings(settings),
        prices=PriceTable(OPENAI_PRICES),
        ledger=durable,
        monthly_cap_usd=settings.llm_monthly_budget_usd,
        run_cap_usd=run_cap_usd,
    )
