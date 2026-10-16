"""Bind durable Agent ownership to existing nested model-call ownership guards.

This is an internal guard factory, not a production loop driver or an HTTP API.
Connections are closed on each check; the provider never inherits a transaction.
"""

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from medops.application.agent_loop_ports import AgentLoopAbort
from medops.core.errors import BusinessError
from medops.domain.agent_execution import AgentContext
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.db.agent_facts import FactDatabaseBinding


def agent_lease_guard(
    connection: Callable[[], AbstractContextManager[Any]],
    context: AgentContext,
    lease: AgentLease,
    *,
    database_binding: FactDatabaseBinding,
) -> Callable[[], None]:
    def guard() -> None:
        try:
            with connection() as conn:
                conn.execute("select set_config('medops.dept',%s,true)", (context.principal.dept.value,))
                PgAgentControl(conn, context, database_binding=database_binding).assert_owned(lease)
        except AgentLoopAbort:
            raise
        except BusinessError:
            raise AgentLoopAbort("lease_lost") from None
        except Exception:  # noqa: BLE001 - no connection strings or directory contents in errors
            raise AgentLoopAbort("dependency_error") from None

    return guard
