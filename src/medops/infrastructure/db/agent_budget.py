"""Fenced, one-shot frozen budget handoff. Caller commits before activating a root."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.core.canonical import canonical_hash
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, advances_budget


@dataclass(frozen=True)
class BudgetHandoff:
    revision: int
    state: FrozenBudgetState
    expires_at: datetime
    claimed: bool


class PgAgentBudget:
    def __init__(self, control: PgAgentControl):
        self.control = control
        self.conn: Any = control.conn

    def _read(self) -> BudgetHandoff | None:
        row = self.conn.execute(
            "select revision,state_sha256,state,budget_expires_at,claimed_lease from agent_budget_handoffs where run_id=%s for update",
            (self.control.context.identity.run_id,),
        ).fetchone()
        if row is None:
            return None
        if canonical_hash(row[2]) != row[1]:
            raise AgentLoopAbort("unsupported_recovery")
        return BudgetHandoff(int(row[0]), FrozenBudgetState.model_validate(row[2]), row[3], row[4] is not None)

    def save(
        self, lease: AgentLease, state: FrozenBudgetState, *, expected_revision: int, expires_at: datetime
    ) -> BudgetHandoff:
        self.control.fence(lease)
        state = FrozenBudgetState.model_validate(state.model_dump(mode="json"))
        prior = self._read()
        if (
            type(expected_revision) is not int
            or expected_revision < 0
            or (
                (prior is None and expected_revision != 0)
                or (
                    prior is not None
                    and (
                        prior.revision != expected_revision
                        or not prior.claimed
                        or not advances_budget(prior.state, state)
                    )
                )
            )
        ):
            raise AgentLoopAbort("unsupported_recovery")
        control = self.control.get()
        if expires_at.tzinfo is None or expires_at > control.expires_at:
            raise AgentLoopAbort("unsupported_recovery")
        if prior is not None:
            expires_at = min(expires_at, prior.expires_at)
        snapshot = state.snapshot
        profile = self.control.context.profile
        if (
            snapshot.limits.token_limit > profile.token_cap
            or snapshot.limits.cost_limit_usd * 1_000_000 > profile.cost_cap_microusd + 1e-6
            or snapshot.limits.timeout_s > profile.timeout_ms / 1000
        ):
            raise AgentLoopAbort("budget_exceeded")
        revision = expected_revision + 1
        identity = self.control.context.principal
        params = dict(
            run=lease.run_id,
            principal=identity.user_id,
            dept=identity.dept.value,
            revision=revision,
            checkpoint=state.checkpoint_id,
            sha=canonical_hash(state.model_dump(mode="json")),
            state=Jsonb(state.model_dump(mode="json")),
            end=expires_at,
        )
        if prior is None:
            self.conn.execute(
                """insert into agent_budget_handoffs
                (run_id,principal,dept,revision,checkpoint_id,state_sha256,state,budget_expires_at)
                values (%(run)s,%(principal)s,%(dept)s,%(revision)s,%(checkpoint)s,%(sha)s,%(state)s,%(end)s)""",
                params,
            )
        else:
            self.conn.execute(
                """update agent_budget_handoffs set revision=%(revision)s,checkpoint_id=%(checkpoint)s,
                state_sha256=%(sha)s,state=%(state)s,budget_expires_at=%(end)s,claimed_lease=null,claimed_generation=null where run_id=%(run)s""",
                params,
            )
        return BudgetHandoff(revision, state, expires_at, False)

    def claim(self, lease: AgentLease, *, expected_revision: int) -> BudgetHandoff:
        self.control.fence(lease)
        record = self._read()
        if (
            type(expected_revision) is not int
            or record is None
            or record.claimed
            or record.revision != expected_revision
        ):
            raise AgentLoopAbort("unsupported_recovery")
        now = self.conn.execute("select clock_timestamp()").fetchone()[0]
        if record.expires_at <= now:
            raise AgentLoopAbort("timeout")
        self.conn.execute(
            """update agent_budget_handoffs set claimed_lease=%s,claimed_generation=%s where run_id=%s""",
            (lease.lease_id, lease.generation, lease.run_id),
        )
        return BudgetHandoff(record.revision, record.state, record.expires_at, True)
