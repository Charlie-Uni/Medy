"""Independent fact reads; only the final fact fence lives through result commit."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from typing import Any, Literal

from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tool_results import AgentFact
from medops.domain.agent_execution import AgentContext
from medops.domain.evidence import Evidence
from medops.infrastructure.db.agent_control import AgentLease, PgAgentControl
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts


class AgentFactScope:
    def __init__(
        self,
        connection: Callable[[], AbstractContextManager[Any]],
        context: AgentContext,
        lease: AgentLease,
        binding: FactDatabaseBinding,
        check_bindings: Callable[[Any, AgentContext], None],
    ):
        self.connection, self.context, self.lease, self.binding = connection, context, lease, binding
        self.check_bindings = check_bindings
        self._stack = ExitStack()
        self.final_connection: Any = None
        self.closed = False

    def __enter__(self) -> AgentFactScope:
        return self

    def __exit__(self, *exc: Any) -> None:
        if not self.closed:
            self.closed = True
            self._stack.__exit__(*exc)

    def _facts(self, conn: Any, *, fence: bool = False) -> PgAgentFacts:
        conn.execute("select set_config('medops.dept',%s,true)", (self.context.principal.dept.value,))
        control = PgAgentControl(conn, self.context, database_binding=self.binding)
        (control.fence if fence else control.assert_owned)(self.lease)
        self.check_bindings(conn, self.context)
        return PgAgentFacts(conn, self.context.principal, database_binding=self.binding)

    def check(self, context: AgentContext) -> None:
        with self.connection() as conn:
            self._facts(conn).check(context)

    def sources(self, context: AgentContext) -> None:
        with self.connection() as conn:
            self._facts(conn).sources(context)

    def lookup(self, context: AgentContext, chunk_ids: tuple[str, ...]) -> tuple[AgentFact, ...]:
        with self.connection() as conn:
            return self._facts(conn).lookup(context, chunk_ids)

    def read(
        self, context: AgentContext, evidence: Evidence, region: Literal["current", "previous", "next"]
    ) -> AgentFact | None:
        with self.connection() as conn:
            return self._facts(conn).read(context, evidence, region)

    def final_check(self, context: AgentContext, facts: tuple[AgentFact, ...], *, check_sources: bool = True) -> None:
        if self.final_connection is not None or context != self.context:
            raise AgentToolFault("dependency_error")
        conn = self._stack.enter_context(self.connection())
        self._facts(conn, fence=True).final_check(context, facts, check_sources=check_sources)
        self.final_connection = conn

    def completion_connection(self) -> Any:
        if self.final_connection is None:
            self.final_connection = self._stack.enter_context(self.connection())
            self._facts(self.final_connection, fence=True).check(self.context)
        return self.final_connection

    def commit(self) -> None:
        if self.closed:
            raise AgentToolFault("dependency_error")
        self.closed = True
        self._stack.close()
