"""Durable business-case admission for Agent control, including process recovery.

Accounting and retained-result reads deliberately do not call this live fence.
"""

from typing import Any

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.core.canonical import canonical_hash
from medops.domain.agent_execution import AgentContext


def guard_registered_case(conn: Any, context: AgentContext) -> str | None:
    """Return the bound command digest; None means an ordinary unregistered case."""
    # Older schemas cannot contain registered cases. 0033 refuses a normal
    # downgrade while any case/grant remains. Keep ordinary pre-case Agent
    # control compatible without treating an occupied case as a new execution.
    if conn.execute("select to_regclass('agent_clarification_cases')").fetchone()[0] is None:
        return None
    row = conn.execute(
        """select principal,dept,current_run_id,expires_at,deleted_at from agent_clarification_cases
        where case_id=%s for update""",
        (context.identity.case_id,),
    ).fetchone()
    if row is None:
        return None
    if row[0] != context.principal.user_id or row[1] != context.principal.dept.value:
        raise AgentLoopAbort("safety_boundary")
    if row[4] is not None:
        raise AgentLoopAbort("cancelled")
    if row[2] != context.identity.run_id:
        raise AgentLoopAbort("version_conflict")
    allocation = conn.execute(
        """select e.context_sha256,e.settled,b.expires_at,e.request_sha256 from agent_clarification_executions e
        join agent_clarification_batches b on b.batch_id=e.batch_id
        where e.run_id=%s and e.case_id=%s and e.principal=%s and e.dept=%s""",
        (context.identity.run_id, context.identity.case_id, context.principal.user_id, context.principal.dept.value),
    ).fetchone()
    if allocation is None or allocation[1] or allocation[0] != canonical_hash(context.model_dump(mode="json")):
        raise AgentLoopAbort("version_conflict")
    now = conn.execute("select clock_timestamp()").fetchone()[0]
    if row[3] <= now or allocation[2] <= now:
        raise AgentLoopAbort("timeout")
    return allocation[3]
