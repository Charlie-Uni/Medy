"""Assemble one PV action from existing production resources; does not start a run.

The caller supplies an authenticated context and application-role transaction, owns
the root allowance/deadline, and must store/commit before another planning/tool call.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from medops.application.agent_tool_ports import AgentToolFault
from medops.application.agent_tools import AgentTools
from medops.application.contracts import AskRequest, HistoricalRequest
from medops.domain.agent_execution import AgentContext
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillContext

if TYPE_CHECKING:
    from medops.bootstrap.runtime import ProductionRuntime


def build_agent_tools(
    runtime: ProductionRuntime, conn: Any, context: AgentContext, *, database_binding: FactDatabaseBinding
) -> AgentTools:
    facts = PgAgentFacts(conn, context.principal, database_binding=database_binding)
    facts.check(context)
    selected = context.query_context
    request = AskRequest(
        query=context.narrative,
        historical=HistoricalRequest(as_of=selected.as_of) if selected.historical_requested else None,
    )
    routed = runtime.route_policies(conn, context.principal)
    if routed.versions != context.versions.versions:
        raise AgentToolFault("dependency_error")
    deps = runtime.build_deps(conn, context.principal, request, routed, query_context=selected)
    limits = context.profile
    if (
        deps.execution_limits is None
        or deps.execution_limits.token_limit > limits.token_cap
        or deps.execution_limits.cost_limit_usd > limits.cost_cap_microusd / 1_000_000
    ):
        raise AgentToolFault("dependency_error")
    # AgentTools pins claim lookups to the handle's facts; no other Skill can be selected.
    skill = SkillContext(
        user=context.principal,
        versions=routed.versions,
        deps=replace(deps, as_of=selected.as_of),
        evidence_lookup=lambda _user, _ids: (),
        doc_type_lookup=lambda _user, _ids: {},
        trace_id=context.identity.trace_id,
        run_id=str(context.identity.run_id),
        as_of=selected.as_of,
    )
    return AgentTools(context=context, facts=facts, registry=default_registry(), skill_context=skill)
