"""Short identity-fenced clarification transactions; no provider calls or business text."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from medops.application.agent_continuation import (
    ClarificationCase,
    ClarificationExecution,
    ClarificationPolicy,
    ContinuationAuthorization,
)
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_runtime_envelope import head_aad
from medops.application.agent_terminal import AgentDelivery
from medops.application.agent_trace import AgentTraceMetadata
from medops.core.canonical import canonical_hash
from medops.core.envelope import KeyProvider, Sealed, open_sealed
from medops.core.money import usd_to_microusd
from medops.core.strict_json import strict_json
from medops.domain.agent_execution import AgentContext
from medops.domain.identity import UserContext
from medops.infrastructure.db.agent_case_fence import guard_registered_case
from medops.infrastructure.db.agent_control import PgAgentControl
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.db.agent_runtime import MAX_RUNTIME_BYTES, PgAgentRuntime
from medops.infrastructure.db.final_output import acquire_output_fence, directory_user, require_same_user


def terminal_accounting(conn: Any, delivery: AgentDelivery) -> tuple[int, int]:
    context = delivery.run.context
    row = conn.execute(
        "select agent_metadata from traces where trace_id=%s and principal=%s and dept=%s and kind='agent'",
        (context.identity.trace_id, context.principal.user_id, context.principal.dept.value),
    ).fetchone()
    if row is None or delivery.run.terminal is None:
        raise AgentLoopAbort("audit_failure")
    metadata = AgentTraceMetadata.model_validate(row[0])
    accounted = usd_to_microusd(metadata.accounting.accounted_cost_usd)
    known = usd_to_microusd(metadata.accounting.known_cost_usd)
    if (
        metadata.run_id != context.identity.run_id
        or metadata.case_id != context.identity.case_id
        or metadata.context_sha256 != canonical_hash(context.model_dump(mode="json"))
        or metadata.terminal_material_ref != delivery.run.terminal.material_ref
        or metadata.terminal_material_sha256 != delivery.run.terminal.material_sha256
        or metadata.status != delivery.run.status
        or not metadata.accounting_complete
        or metadata.pending_calls
        or metadata.accounting.reserved_cost_usd
        or accounted != delivery.run.budget.accounted_cost_microusd
        or known > accounted
    ):
        raise AgentLoopAbort("audit_failure")
    return accounted, known


def owned_context(
    conn: Any, user: UserContext, run_id: UUID, *, provider: KeyProvider, database_binding: FactDatabaseBinding
) -> AgentContext:
    """Authenticated, bounded owner lookup. Does not restore any executable root."""
    access = PgAgentClarification(conn, user)
    access._access()
    row = conn.execute(
        """select h.context_sha256,h.revision,h.lease_id,h.lease_generation,h.budget_state,h.budget_deadline,
        h.retained_until,h.ciphertext,h.nonce,h.dek_wrapped,h.kek_version from agent_runtime_heads h
        join agent_run_control c using(run_id) where h.run_id=%s and h.principal=%s and h.dept=%s
        and c.principal=h.principal and c.dept=h.dept and c.context_sha256=h.context_sha256
        and h.retained_until>clock_timestamp()""",
        (run_id, user.user_id, user.dept.value),
    ).fetchone()
    if row is None:
        raise AgentLoopAbort("safety_boundary")
    if len(row[7]) > MAX_RUNTIME_BYTES + 16:
        raise AgentLoopAbort("audit_failure")
    raw = open_sealed(
        Sealed(bytes(row[7]), bytes(row[8]), bytes(row[9]), row[10]),
        provider=provider,
        aad=head_aad(run_id, row[0], row[1], row[2], row[3], row[4], row[5], row[6]),
    )
    body = strict_json(raw)
    if not isinstance(body, dict) or not isinstance(body.get("run"), dict):
        raise AgentLoopAbort("audit_failure")
    context = AgentContext.model_validate(body["run"].get("context"))
    if (
        context.principal != user
        or context.identity.run_id != run_id
        or canonical_hash(context.model_dump(mode="json")) != row[0]
    ):
        raise AgentLoopAbort("audit_failure")
    control = PgAgentControl(conn, context, database_binding=database_binding)
    return PgAgentRuntime(control, provider).read().body.run.context


class PgAgentClarification:
    def __init__(self, conn: Any, user: UserContext):
        self.conn, self.user = conn, user

    def _access(self) -> None:
        acquire_output_fence(self.conn)
        self.conn.execute("select set_config('medops.dept',%s,true)", (self.user.dept.value,))
        require_same_user(self.user, directory_user(self.conn, self.user))
        if not self.user.has_scopes((f"{self.user.dept.value}:read",)):
            raise AgentLoopAbort("safety_boundary")

    def _now(self):
        return self.conn.execute("select clock_timestamp()").fetchone()[0]

    def batch(self, authorization: ContinuationAuthorization) -> None:
        self._access()
        if authorization.expires_at <= self._now():
            raise AgentLoopAbort("timeout")
        data = authorization.model_dump(mode="json")
        self.conn.execute(
            """insert into agent_clarification_batches
            (batch_id,principal,dept,authorization_sha256,case_ids,expires_at,max_executions,cost_limit_microusd)
            values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict(batch_id) do nothing""",
            (
                authorization.batch_id,
                self.user.user_id,
                self.user.dept.value,
                canonical_hash(data),
                list(authorization.case_ids),
                authorization.expires_at,
                authorization.max_executions,
                authorization.cost_limit_microusd,
            ),
        )
        row = self.conn.execute(
            "select principal,dept,authorization_sha256 from agent_clarification_batches where batch_id=%s",
            (authorization.batch_id,),
        ).fetchone()
        if row != (self.user.user_id, self.user.dept.value, canonical_hash(data)):
            raise AgentLoopAbort("version_conflict")

    def open_case(
        self, context: AgentContext, policy: ClarificationPolicy, *, source_cost: int, known_cost: int
    ) -> ClarificationCase:
        self._access()
        source = self.conn.execute(
            """select started_at from agent_run_control where run_id=%s and principal=%s and dept=%s
            and case_id=%s and context_sha256=%s and terminal_status='awaiting_clarification'""",
            (
                context.identity.run_id,
                self.user.user_id,
                self.user.dept.value,
                context.identity.case_id,
                canonical_hash(context.model_dump(mode="json")),
            ),
        ).fetchone()
        if source is None:
            raise AgentLoopAbort("unsupported_requirement")
        expires = source[0] + timedelta(seconds=policy.ttl_seconds)
        if expires <= self._now():
            raise AgentLoopAbort("timeout")
        if source_cost > policy.cost_limit_microusd:
            raise AgentLoopAbort("budget_exceeded")
        self.conn.execute(
            """insert into agent_clarification_cases
            (case_id,principal,dept,initial_run_id,initial_context_sha256,policy_sha256,expires_at,
             max_continuations,cost_limit_microusd,current_run_id)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(case_id) do nothing""",
            (
                context.identity.case_id,
                self.user.user_id,
                self.user.dept.value,
                context.identity.run_id,
                canonical_hash(context.model_dump(mode="json")),
                canonical_hash(policy.model_dump(mode="json")),
                expires,
                policy.max_continuations,
                policy.cost_limit_microusd,
                context.identity.run_id,
            ),
        )
        row = self._case(context.identity.case_id, lock=True)
        if row[0] != context.identity.run_id or row[7] != canonical_hash(policy.model_dump(mode="json")):
            raise AgentLoopAbort("version_conflict")
        self.conn.execute(
            """insert into agent_clarification_executions
            (run_id,case_id,principal,dept,context_sha256,ordinal,accounted_cost_microusd,known_cost_microusd,held_cost_microusd,settled)
            values (%s,%s,%s,%s,%s,0,%s,%s,0,true) on conflict(run_id) do nothing""",
            (
                context.identity.run_id,
                context.identity.case_id,
                self.user.user_id,
                self.user.dept.value,
                canonical_hash(context.model_dump(mode="json")),
                source_cost,
                known_cost,
            ),
        )
        return self.read(context.identity.case_id)

    def _case(self, case_id: UUID, *, lock=False):
        self._access()
        row = self.conn.execute(
            """select initial_run_id,current_run_id,revision,expires_at,deleted_at,max_continuations,
            cost_limit_microusd,policy_sha256 from agent_clarification_cases
            where case_id=%s and principal=%s and dept=%s"""
            + (" for update" if lock else ""),
            (case_id, self.user.user_id, self.user.dept.value),
        ).fetchone()
        if row is None:
            raise AgentLoopAbort("safety_boundary")
        return row

    def _live(self, row) -> None:
        if row[4] is not None:
            raise AgentLoopAbort("cancelled")
        if row[3] <= self._now():
            raise AgentLoopAbort("timeout")

    def read(self, case_id: UUID) -> ClarificationCase:
        # Keep revision/current-run stable until the aggregate read commits.
        # READ COMMITTED alone could combine an old revision with a new run's fees.
        row = self._case(case_id, lock=True)
        totals = self.conn.execute(
            """select count(*) filter(where ordinal>0),coalesce(sum(accounted_cost_microusd),0),
            coalesce(sum(held_cost_microusd),0),coalesce(sum(known_cost_microusd),0)
            from agent_clarification_executions where case_id=%s""",
            (case_id,),
        ).fetchone()
        return ClarificationCase(
            case_id=case_id,
            initial_run_id=row[0],
            current_run_id=row[1],
            revision=row[2],
            expires_at=row[3],
            deleted_at=row[4],
            continuations=int(totals[0]),
            accounted_cost_microusd=int(totals[1]),
            known_cost_microusd=int(totals[3]),
            held_cost_microusd=int(totals[2]),
        )

    def executions(self, case_id: UUID, *, after_ordinal: int, limit: int) -> tuple[ClarificationExecution, ...]:
        self._case(case_id)
        if type(after_ordinal) is not int or after_ordinal < -1 or type(limit) is not int or not 1 <= limit <= 64:
            raise AgentLoopAbort("unsupported_requirement")
        rows = self.conn.execute(
            """select run_id,source_run_id,batch_id,ordinal,accounted_cost_microusd,
            known_cost_microusd,held_cost_microusd,settled from agent_clarification_executions
            where case_id=%s and principal=%s and dept=%s and ordinal>%s order by ordinal limit %s""",
            (case_id, self.user.user_id, self.user.dept.value, after_ordinal, limit),
        ).fetchall()
        keys = tuple(ClarificationExecution.model_fields)
        return tuple(ClarificationExecution.model_validate(dict(zip(keys, row, strict=True))) for row in rows)

    def command(self, command_id: UUID):
        self._access()
        return self.conn.execute(
            """select run_id,case_id,request_sha256,context_sha256,settled from agent_clarification_executions
            where command_id=%s and principal=%s and dept=%s""",
            (command_id, self.user.user_id, self.user.dept.value),
        ).fetchone()

    def reserve(
        self,
        context: AgentContext,
        *,
        command_id: UUID,
        batch_id: UUID,
        source_run_id: UUID,
        request_sha256: str,
        expected_revision: int,
    ) -> None:
        self._access()
        # All allocating transactions lock batch -> case. Across cases this is
        # the shared grant ceiling; a new task or process cannot reset it.
        batch = self.conn.execute(
            """select case_ids,expires_at,max_executions,cost_limit_microusd from agent_clarification_batches
            where batch_id=%s and principal=%s and dept=%s for update""",
            (batch_id, self.user.user_id, self.user.dept.value),
        ).fetchone()
        if batch is None or context.identity.case_id not in batch[0]:
            raise AgentLoopAbort("safety_boundary")
        row = self._case(context.identity.case_id, lock=True)
        self._live(row)
        if batch[1] <= self._now():
            raise AgentLoopAbort("timeout")
        if row[2] != expected_revision or row[1] != source_run_id:
            raise AgentLoopAbort("version_conflict")
        case = self.read(context.identity.case_id)
        totals = self.conn.execute(
            """select count(*),coalesce(sum(accounted_cost_microusd+held_cost_microusd),0)
            from agent_clarification_executions where batch_id=%s""",
            (batch_id,),
        ).fetchone()
        cap = context.profile.cost_cap_microusd
        if (
            case.continuations >= row[5]
            or case.accounted_cost_microusd + case.held_cost_microusd + cap > row[6]
            or totals[0] >= batch[2]
            or int(totals[1]) + cap > batch[3]
        ):
            raise AgentLoopAbort("budget_exceeded")
        # Never reuse a surviving execution/Trace identity, even if encrypted
        # material has since been purged. The command row is also a tombstone.
        if (
            self.conn.execute("select 1 from agent_run_control where run_id=%s", (context.identity.run_id,)).fetchone()
            or self.conn.execute("select 1 from traces where trace_id=%s", (context.identity.trace_id,)).fetchone()
        ):
            raise AgentLoopAbort("version_conflict")
        self.conn.execute(
            """insert into agent_clarification_executions
            (run_id,case_id,principal,dept,command_id,batch_id,source_run_id,request_sha256,context_sha256,
             ordinal,accounted_cost_microusd,known_cost_microusd,held_cost_microusd,settled)
            values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,%s,false)""",
            (
                context.identity.run_id,
                context.identity.case_id,
                self.user.user_id,
                self.user.dept.value,
                command_id,
                batch_id,
                source_run_id,
                request_sha256,
                canonical_hash(context.model_dump(mode="json")),
                case.continuations + 1,
                cap,
            ),
        )
        self.conn.execute(
            "update agent_clarification_cases set current_run_id=%s,revision=revision+1 where case_id=%s",
            (context.identity.run_id, context.identity.case_id),
        )

    def guard(self, context: AgentContext, *, request_sha256: str) -> None:
        self._access()
        if context.principal != self.user:
            raise AgentLoopAbort("safety_boundary")
        if guard_registered_case(self.conn, context) != request_sha256:
            raise AgentLoopAbort("version_conflict")

    def settle(self, context: AgentContext, *, delivery: AgentDelivery) -> None:
        # Accounting-only cleanup, deliberately not the case live/permission
        # guard: deletion/revocation must not erase already incurred costs.
        self.conn.execute("select set_config('medops.dept',%s,true)", (self.user.dept.value,))
        if delivery.run.context != context:
            raise AgentLoopAbort("audit_failure")
        source_cost, known_cost = terminal_accounting(self.conn, delivery)
        row = self.conn.execute(
            """select context_sha256,settled,accounted_cost_microusd from agent_clarification_executions
            where run_id=%s and case_id=%s and principal=%s and dept=%s for update""",
            (context.identity.run_id, context.identity.case_id, self.user.user_id, self.user.dept.value),
        ).fetchone()
        if row is None or row[0] != canonical_hash(context.model_dump(mode="json")):
            raise AgentLoopAbort("audit_failure")
        if row[1]:
            if row[2] != source_cost:
                raise AgentLoopAbort("audit_failure")
            return
        self.conn.execute(
            """update agent_clarification_executions set accounted_cost_microusd=%s,known_cost_microusd=%s,held_cost_microusd=0,settled=true
            where run_id=%s""",
            (source_cost, known_cost, context.identity.run_id),
        )

    def delete(self, case_id: UUID, *, expected_revision: int) -> ClarificationCase:
        if type(expected_revision) is not int or expected_revision < 1:
            raise AgentLoopAbort("version_conflict")
        row = self._case(case_id, lock=True)
        if row[2] != expected_revision or row[4] is not None:
            raise AgentLoopAbort("version_conflict")
        self.conn.execute(
            "update agent_clarification_cases set deleted_at=clock_timestamp(),revision=revision+1 where case_id=%s",
            (case_id,),
        )
        return self.read(case_id)
