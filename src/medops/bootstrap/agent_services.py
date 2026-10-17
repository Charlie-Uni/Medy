"""Production resources for the durable PV Agent, with independent fact reads.

Only trusted startup may bind a NEW private context. Existing runs never acquire
today's versions or a fresh budget through this composition function.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from medops.application.agent_final_gate import FinalGateConfig, derived_profile, policy_sha256
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_planning import PlannerConfig, planning_prompt_sha256
from medops.application.agent_tools import tool_contract_sha256
from medops.bootstrap.agent_driver import AgentResources
from medops.bootstrap.agent_execution import AgentRuntime
from medops.bootstrap.retrieval import execution_binding
from medops.core.canonical import canonical_hash
from medops.domain.agent_execution import AgentContext
from medops.domain.identity import UserContext
from medops.harness.answer import ANSWER_SYSTEM
from medops.harness.dependencies import HarnessDeps
from medops.harness.production import PRODUCTION_ANSWER_MODEL, PRODUCTION_JUDGE_MODEL
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts
from medops.infrastructure.db.final_output import directory_user, require_same_user
from medops.infrastructure.llm.execution_budget import configured_limits
from medops.infrastructure.llm.meter import MeteredGateway
from medops.retrieval.doc_focus import load_titles
from medops.retrieval.production import RERANK_OUTPUT
from medops.safety.checks import SAFETY_VERSION
from medops.skills.catalog import default_registry
from medops.skills.production import doc_type_lookup, evidence_lookup
from medops.skills.registry import SkillContext
from medops.verification.verifier import VERIFIER_VERSION

if TYPE_CHECKING:
    from medops.bootstrap.runtime import ProductionRuntime


def _verification(final_config: FinalGateConfig) -> str:
    return canonical_hash(
        {
            "safety": SAFETY_VERSION,
            "verifier": VERIFIER_VERSION,
            "tools": tool_contract_sha256(),
            "final": policy_sha256(final_config),
        }
    )


def _conditions(routed: Any, config: PlannerConfig, final_config: FinalGateConfig) -> str:
    return canonical_hash(
        {
            "execution": execution_binding(routed),
            "planner": config.model_dump(mode="json"),
            "verification": _verification(final_config),
            "runtime": "pv-agent-runtime-v1",
        }
    )


def bind_new_agent_context(
    runtime: ProductionRuntime,
    context: AgentContext,
    *,
    config: PlannerConfig,
    final_config: FinalGateConfig,
    database_binding: FactDatabaseBinding,
) -> AgentContext:
    """Server-only preparation, BEFORE control creation; never a recovery adapter.

    Profile, narrative/requirements, rubric identity and source scope come from
    the trusted admission layer. No model/candidate may call this function.
    """
    with runtime.connection() as conn:
        runtime.bind_identity(conn, context.principal)
        require_same_user(context.principal, directory_user(conn, context.principal))
        if conn.execute("select 1 from agent_run_control where run_id=%s", (context.identity.run_id,)).fetchone():
            raise AgentLoopAbort("unsupported_recovery")
        routed = runtime.route_policies(conn, context.principal)
        facts = PgAgentFacts(conn, context.principal, database_binding=database_binding)
        if context.source_scope.resolution == "resolved":
            facts.sources(context)
        versions = context.versions.model_copy(
            update={
                "versions": routed.versions,
                "planning_prompt_sha256": planning_prompt_sha256(),
                "tool_contract_sha256": tool_contract_sha256(),
                "verification_policy_sha256": _verification(final_config),
                "fact_database_id": database_binding.fact_database_id,
                "fact_conditions_sha256": _conditions(routed, config, final_config),
            }
        )
    return AgentContext.model_validate(
        context.model_copy(
            update={
                "versions": versions,
                "profile": derived_profile(context, final_config, MeteredGateway(runtime.gateway).execution_prices),
            }
        ).model_dump(mode="json")
    )


def production_agent_runtime(
    runtime: ProductionRuntime,
    context: AgentContext,
    *,
    config: PlannerConfig,
    final_config: FinalGateConfig,
    database_binding: FactDatabaseBinding,
    lease_s: float,
) -> AgentRuntime:
    if final_config.model_id != PRODUCTION_JUDGE_MODEL:
        raise AgentLoopAbort("version_conflict")
    if runtime._key_provider is None:
        raise AgentLoopAbort("audit_failure")

    def connection():
        # Independent connection; no request transaction is captured by a tool
        # or held through planning/AE/citation provider work.
        return runtime._open(runtime._dsn)

    def check_bindings(conn: Any, ctx: AgentContext) -> None:
        routed = runtime.route_policies(conn, ctx.principal)
        if (
            routed.versions != ctx.versions.versions
            or _conditions(routed, config, final_config) != ctx.versions.fact_conditions_sha256
            or _verification(final_config) != ctx.versions.verification_policy_sha256
        ):
            raise AgentLoopAbort("version_conflict")

    def resources(ctx: AgentContext, meter: MeteredGateway) -> AgentResources:
        if ctx != context:
            raise AgentLoopAbort("version_conflict")
        with connection() as conn:
            runtime.bind_identity(conn, ctx.principal)
            require_same_user(ctx.principal, directory_user(conn, ctx.principal))
            check_bindings(conn, ctx)
            routed = runtime.route_policies(conn, ctx.principal)

        @contextmanager
        def for_user(user: UserContext) -> Iterator[Any]:
            if user != ctx.principal:
                raise AgentLoopAbort("safety_boundary")
            with connection() as conn:
                runtime.bind_identity(conn, user)
                require_same_user(user, directory_user(conn, user))
                check_bindings(conn, ctx)
                yield conn

        retrieval = runtime.retrieval_services.build(
            None, ctx.principal, ctx.query_context, routed, meter, connection_for_user=for_user
        )
        scorer = runtime.retrieval_services.reranker_for(routed.policies.rerank_output(RERANK_OUTPUT))

        def titles(user: UserContext, ids: Any) -> Any:
            with for_user(user) as conn:
                return load_titles(conn, ids)

        deps = HarnessDeps(
            retrieval=retrieval,
            gateway=meter,
            answer_system=routed.policies.answer_system(ANSWER_SYSTEM),
            answer_model_id=PRODUCTION_ANSWER_MODEL,
            judge_model_id=PRODUCTION_JUDGE_MODEL,
            answer_model_by_intent=routed.policies.answer_models(),
            evidence_focus=routed.policies.evidence_focus(),
            sentence_scorer=scorer.score,
            doc_titles=titles,
            as_of=ctx.query_context.as_of,
            query_context=ctx.query_context,
            execution_limits=configured_limits(runtime.settings),
            execution_binding=execution_binding(routed),
        )
        skill = SkillContext(
            user=ctx.principal,
            versions=routed.versions,
            deps=deps,
            evidence_lookup=evidence_lookup(
                for_user, as_of=ctx.query_context.as_of, allow_historical=ctx.query_context.historical_requested
            ),
            doc_type_lookup=doc_type_lookup(for_user),
            trace_id=ctx.identity.trace_id,
            run_id=str(ctx.identity.run_id),
            as_of=ctx.query_context.as_of,
        )
        return AgentResources(default_registry(), skill, check_bindings, final_config)

    return AgentRuntime(
        connection=connection,
        gateway=runtime.gateway,
        provider=runtime._key_provider,
        database_binding=database_binding,
        config=config,
        limits=configured_limits(runtime.settings),
        resources=resources,
        lease_s=lease_s,
        retention_days=runtime.settings.payload_retention_days,
    )
