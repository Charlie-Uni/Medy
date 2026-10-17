"""Explicit frozen-budget transfer, with commit-before-activation and no model calls.

This is not a production Agent driver or a whole-loop restore API. A new owner
must still validate all observations and current facts before any future step.
"""

import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from medops.application.agent_contracts import validate_run_snapshot
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.core.money import usd_to_microusd
from medops.domain.agent_execution import PVAgentRun
from medops.infrastructure.db.agent_budget import BudgetHandoff, PgAgentBudget
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, restore_consumed_budget
from medops.infrastructure.llm.execution_budget import ExecutionBudget, current_budget

Connection = Callable[[], AbstractContextManager[Any]]


@dataclass(frozen=True)
class RestoredAgentBudget:
    budget: ExecutionBudget
    revision: int


def _bind(conn: Any, run: PVAgentRun, lease: AgentLease, binding: FactDatabaseBinding) -> PgAgentControl:
    conn.execute("select set_config('medops.dept',%s,true)", (run.context.principal.dept.value,))
    control = PgAgentControl(conn, run.context, database_binding=binding)
    control.fence(lease)
    stored = control.get()
    if (stored.started_at, stored.expires_at, stored.decisions_consumed) != (
        run.started_at,
        run.expires_at,
        run.decisions_consumed,
    ):
        raise AgentLoopAbort("unsupported_recovery")
    return control


def _matches(run: PVAgentRun, state: FrozenBudgetState) -> None:
    snapshot = state.snapshot
    actual = (
        snapshot.accounted_tokens,
        snapshot.reserved_tokens,
        usd_to_microusd(snapshot.accounted_cost_usd),
        usd_to_microusd(snapshot.reserved_cost_usd),
    )
    claimed = run.budget
    if actual != (
        claimed.accounted_tokens,
        claimed.reserved_tokens,
        claimed.accounted_cost_microusd,
        claimed.reserved_cost_microusd,
    ):
        raise AgentLoopAbort("unsupported_recovery")


def persist_agent_budget(
    connection: Connection,
    *,
    run: PVAgentRun,
    lease: AgentLease,
    expected_revision: int,
    database_binding: FactDatabaseBinding,
) -> BudgetHandoff:
    run = validate_run_snapshot(run)
    budget = current_budget()
    if budget is None or run.status != "running":
        raise AgentLoopAbort("unsupported_recovery")
    started = time.monotonic()
    state = FrozenBudgetState.model_validate(budget.freeze_state())
    _matches(run, state)
    # A failure below leaves the old root suspended. Retrying with a new zero root
    # would be unsafe; the caller must stop and retain its accounting/audit.
    with connection() as conn:
        control = _bind(conn, run, lease, database_binding)
        now = conn.execute("select clock_timestamp()").fetchone()[0]
        expires = min(
            run.expires_at, now + timedelta(seconds=max(0, state.remaining_timeout_s - (time.monotonic() - started)))
        )
        record = PgAgentBudget(control).save(lease, state, expected_revision=expected_revision, expires_at=expires)
    return record


def restore_agent_budget(
    connection: Connection,
    *,
    run: PVAgentRun,
    lease: AgentLease,
    expected_revision: int,
    database_binding: FactDatabaseBinding,
) -> RestoredAgentBudget:
    run = validate_run_snapshot(run)
    if current_budget() is not None or run.status != "running":
        raise AgentLoopAbort("unsupported_recovery")
    with connection() as conn:
        control = _bind(conn, run, lease, database_binding)
        record = PgAgentBudget(control).claim(lease, expected_revision=expected_revision)
        _matches(run, record.state)
        started = time.monotonic()
        now = conn.execute("select clock_timestamp()").fetchone()[0]
        remaining = min(record.state.remaining_timeout_s, (record.expires_at - now).total_seconds())
    # The claim transaction has committed and closed. Any failed/uncertain commit
    # returns no engine. Its possibly consumed record may not be replayed for free.
    deadline = started + remaining
    if deadline <= time.monotonic():
        raise AgentLoopAbort("timeout")
    budget = restore_consumed_budget(record.state, expires_at_monotonic=deadline)
    return RestoredAgentBudget(budget, record.revision)
