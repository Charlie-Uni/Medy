"""Short, caller-owned transactions for Agent control; never a new execution budget.

Use a fresh READ COMMITTED application connection, bound to the context department.
Commit before calling a model. A final write must call fence() on the *same*
connection as its audit/material writes and commit. No public endpoint or production
AgentLoopDriver is registered by this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from pydantic import Field

from medops.application.agent_contracts import validate_run_snapshot
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.core.canonical import canonical_hash
from medops.domain.agent_actions import AgentModel
from medops.domain.agent_execution import AgentContext, PVAgentRun
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.db.deadline import DeadlineConnection
from medops.infrastructure.db.final_output import acquire_output_fence, directory_user, require_same_user
from medops.retrieval.integrity import database_identity


class AgentLease(AgentModel):
    run_id: UUID
    lease_id: UUID
    generation: Annotated[int, Field(ge=1, strict=True)]


@dataclass(frozen=True)
class AgentControlState:
    run_id: UUID
    decisions_consumed: int
    started_at: datetime
    expires_at: datetime
    lease_id: UUID | None
    lease_generation: int
    lease_until: datetime | None
    cancelled_at: datetime | None


_COLUMNS = "run_id, decisions_consumed, started_at, expires_at, lease_id, lease_generation, lease_until, cancelled_at"


def _lease_seconds(value: float) -> float:
    if isinstance(value, bool) or not math.isfinite(value) or value <= 0 or value > 125:
        raise ValueError("invalid_agent_lease")
    return value


class PgAgentControl:
    def __init__(self, conn: Any, context: AgentContext, *, database_binding: FactDatabaseBinding):
        self.conn: Any = DeadlineConnection(conn)
        self.context = AgentContext.model_validate(context.model_dump(mode="python"))
        self.database_binding = FactDatabaseBinding.model_validate(database_binding.model_dump(mode="python"))
        self._params = {
            "run": context.identity.run_id,
            "principal": context.principal.user_id,
            "dept": context.principal.dept.value,
            "sha": canonical_hash(self.context.model_dump(mode="json")),
        }

    def _access(self) -> None:
        # This shared fact fence also serializes directory revocations with these
        # short writes. Do not hold it over a provider call or between decisions.
        acquire_output_fence(self.conn)
        user = self.context.principal
        dept = self.conn.execute("select current_setting('medops.dept',true)").fetchone()
        if dept is None or dept[0] != user.dept.value or not user.has_scopes((f"{user.dept.value}:read",)):
            raise AgentLoopAbort("lease_lost")
        require_same_user(user, directory_user(self.conn, user))
        if (
            self.database_binding.fact_database_id != self.context.versions.fact_database_id
            or database_identity(self.conn) != self.database_binding.connection_identity
        ):
            raise AgentLoopAbort("version_conflict")

    def create(self, run: PVAgentRun) -> None:
        """Insert once, only for an actually fresh run. A duplicate never resets it."""
        run = validate_run_snapshot(run)
        if (
            run.context != self.context
            or run.status != "running"
            or run.decisions_consumed
            or any(run.budget.model_dump().values())
        ):
            raise AgentLoopAbort("unsupported_recovery")
        self._access()
        now = self.conn.execute("select clock_timestamp()").fetchone()[0]
        if now < run.started_at or now >= run.expires_at:
            raise AgentLoopAbort("timeout")
        identity = self.context.identity
        self.conn.execute(
            """insert into agent_run_control
            (run_id,case_id,task_id,attempt_id,principal,dept,trace_id,context_sha256,started_at,expires_at)
            values (%(run)s,%(case)s,%(task)s,%(attempt)s,%(principal)s,%(dept)s,%(trace)s,%(sha)s,%(start)s,%(end)s)""",
            dict(
                self._params,
                case=identity.case_id,
                task=identity.task_id,
                attempt=identity.attempt_id,
                trace=identity.trace_id,
                start=run.started_at,
                end=run.expires_at,
            ),
        )

    def _read(self, *, lock: bool) -> AgentControlState:
        self._access()
        suffix = " for update" if lock else ""
        row = self.conn.execute(
            f"select {_COLUMNS} from agent_run_control where run_id=%(run)s and principal=%(principal)s and dept=%(dept)s and context_sha256=%(sha)s{suffix}",
            self._params,
        ).fetchone()
        if row is None:
            raise AgentLoopAbort("lease_lost")
        return AgentControlState(*row)

    def get(self) -> AgentControlState:
        return self._read(lock=False)

    def _live(self, state: AgentControlState, lease: AgentLease | None = None) -> datetime:
        # Separate statement: PostgreSQL must obtain any row lock before reading
        # the real clock, including after a lock wait. No caller-supplied clock.
        now = self.conn.execute("select clock_timestamp()").fetchone()[0]
        if state.cancelled_at is not None:
            raise AgentLoopAbort("cancelled")
        if now < state.started_at or now >= state.expires_at:
            raise AgentLoopAbort("timeout")
        if lease is not None and (
            state.run_id != lease.run_id
            or state.lease_id != lease.lease_id
            or state.lease_generation != lease.generation
            or state.lease_until is None
            or state.lease_until <= now
        ):
            raise AgentLoopAbort("lease_lost")
        return now

    def claim(self, lease_s: float) -> AgentLease:
        """Reclaiming fences an old worker; it does not authorize loop recovery."""
        _lease_seconds(lease_s)
        state = self._read(lock=True)
        now = self._live(state)
        if state.lease_until is not None and state.lease_until > now:
            raise AgentLoopAbort("lease_lost")
        lease = AgentLease(run_id=state.run_id, lease_id=uuid4(), generation=state.lease_generation + 1)
        self.conn.execute(
            """update agent_run_control set lease_id=%(id)s,lease_generation=%(gen)s,
            lease_until=least(expires_at,clock_timestamp()+%(seconds)s*interval '1 second')
            where run_id=%(run)s""",
            {"id": lease.lease_id, "gen": lease.generation, "seconds": lease_s, "run": state.run_id},
        )
        return lease

    def assert_owned(self, lease: AgentLease) -> None:
        """Call from a fresh connection before every physical provider call."""
        self._live(self._read(lock=False), lease)

    def fence(self, lease: AgentLease) -> None:
        """Lock through same-transaction result/audit commit; no output is published here."""
        self._live(self._read(lock=True), lease)

    def renew(self, lease: AgentLease, lease_s: float) -> None:
        _lease_seconds(lease_s)
        self.fence(lease)
        self.conn.execute(
            """update agent_run_control set lease_until=greatest(lease_until,
            least(expires_at,clock_timestamp()+%(seconds)s*interval '1 second')) where run_id=%(run)s""",
            {"seconds": lease_s, "run": lease.run_id},
        )

    def consume_decision(self, lease: AgentLease, *, expected_decisions: int) -> int:
        if type(expected_decisions) is not int or not 0 <= expected_decisions < 8:
            raise AgentLoopAbort("step_limit")
        self.fence(lease)
        row = self.conn.execute(
            """update agent_run_control set decisions_consumed=decisions_consumed+1
            where run_id=%(run)s and decisions_consumed=%(expected)s
            and expires_at>clock_timestamp() and lease_until>clock_timestamp() returning decisions_consumed""",
            {"run": lease.run_id, "expected": expected_decisions},
        ).fetchone()
        if row is None:
            raise AgentLoopAbort("unsupported_recovery")
        return int(row[0])

    def cancel(self) -> AgentControlState:
        """Idempotent owner cancellation, retained after connection/process replacement."""
        self._read(lock=True)
        self.conn.execute(
            "update agent_run_control set cancelled_at=clock_timestamp() where run_id=%(run)s and cancelled_at is null",
            self._params,
        )
        return self._read(lock=False)
