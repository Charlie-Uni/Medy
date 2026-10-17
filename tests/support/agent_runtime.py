"""PUBLIC synthetic runtime case: real PG facts/control, offline model/retrieval."""

from contextlib import contextmanager
from datetime import UTC, date, datetime
from threading import local
from uuid import uuid4

import psycopg

from medops.application.agent_final_gate import derived_profile
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_planning import PlannerConfig, planning_prompt_sha256
from medops.application.agent_tools import tool_contract_sha256
from medops.bootstrap.agent_driver import AgentResources
from medops.bootstrap.agent_execution import AgentRuntime
from medops.core.envelope import StaticKeyProvider
from medops.domain.agent_execution import AgentSourceScope, AllowedSource
from medops.infrastructure.db.agent_facts import PgAgentFacts
from medops.infrastructure.llm.execution_budget import ExecutionLimits
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillContext
from tests.support.agent_control import control_data
from tests.support.documents import document, job, source_object
from tests.support.harness import FakeRetrieval, make_deps


def runtime_case(db, gateway, *, lease_s=10, limits=None, final_config=None, narrative_only=False):
    _, base, binding = control_data(db)
    with psycopg.connect(db["owner"]) as conn:
        src = source_object(conn, uuid4().int % 2**55)
        conn.execute(
            "update source_objects set integrity_status='verified',last_verified_at=now() where source_object_id=%s",
            (src,),
        )
        doc = document(
            conn,
            src,
            job(conn, src),
            status="active",
            parse_quality="trusted",
            owner_dept="PV",
            doc_type="guideline",
            version="PUBLIC v1",
            title="PUBLIC runtime guideline",
            effective_from=date(2025, 1, 1),
        )
        conn.execute("insert into document_acl(doc_id,dept,granted_by) values (%s,'PV','PUBLIC-runtime-test')", (doc,))
        text = "PUBLIC runtime clause: the source records the report date."
        chunk = conn.execute(
            "insert into chunks(doc_id,seq,page,section,content) values (%s,0,1,'PUBLIC',%s) returning chunk_id",
            (doc, text),
        ).fetchone()[0]
        conn.execute(
            "insert into chunk_spans(chunk_id,ordinal,page,char_start,char_end) values (%s,0,1,0,%s)",
            (chunk, len(text)),
        )
        sha = conn.execute("select source_hash from source_objects where source_object_id=%s", (src,)).fetchone()[0]
    registry = default_registry(sleep=lambda _: None, clock=lambda: datetime.now(UTC))
    versions = base.context.versions.model_copy(
        update={
            "planning_prompt_sha256": planning_prompt_sha256(),
            "tool_contract_sha256": tool_contract_sha256(registry),
            "versions": base.context.versions.versions.model_copy(update={"skill_version_set": registry.version_set()}),
        }
    )
    context = base.context.model_copy(
        update={
            "versions": versions,
            "identity": base.context.identity.model_copy(update={"trace_id": uuid4().hex}),
            "source_scope": AgentSourceScope(
                requested_document=str(doc),
                requested_version="PUBLIC v1",
                resolution="resolved",
                allowed_sources=(AllowedSource(doc_id=str(doc), version="PUBLIC v1", source_sha256=sha),),
            ),
        }
    )
    if narrative_only:
        context = context.model_copy(
            update={"requirements": tuple(r for r in context.requirements if r.kind == "narrative")}
        )
    if final_config is not None:
        from medops.infrastructure.llm.meter import MeteredGateway

        context = context.model_copy(
            update={"profile": derived_profile(context, final_config, MeteredGateway(gateway).execution_prices)}
        )
    state = reopen_case(
        db,
        base.model_copy(update={"context": context}),
        binding,
        str(chunk),
        gateway,
        lease_s=lease_s,
        limits=limits,
        final_config=final_config,
    )
    state["run"] = state["runtime"].new_run(context)
    return state


def reopen_case(db, run, binding, chunk, gateway, *, lease_s=10, limits=None, final_config=None):
    context = run.context
    registry = default_registry(sleep=lambda _: None, clock=lambda: datetime.now(UTC))
    state = {
        "bindings_valid": True,
        "open": local(),
        "calls": [],
        "context": context,
        "db": db,
        "doc": context.source_scope.allowed_sources[0].doc_id,
        "chunk": str(chunk),
    }

    @contextmanager
    def connection():
        state["open"].count = getattr(state["open"], "count", 0) + 1
        try:
            with psycopg.connect(db["users"]["app"], connect_timeout=2, options="-c statement_timeout=3000") as conn:
                yield conn
        finally:
            state["open"].count -= 1

    def check_bindings(conn, ctx):
        if not state["bindings_valid"] or ctx.versions != context.versions:
            raise AgentLoopAbort("version_conflict")

    def resources(ctx, meter):
        with connection() as conn:
            conn.execute("select set_config('medops.dept','PV',true)")
            fact = PgAgentFacts(conn, ctx.principal, database_binding=binding).lookup(ctx, (str(chunk),))[0]
        retrieval = FakeRetrieval(fact.evidence)
        deps = make_deps(
            retrieval, meter, judge_model_id="gpt-6-sol", as_of=ctx.query_context.as_of, query_context=ctx.query_context
        )
        return AgentResources(
            registry,
            SkillContext(
                user=ctx.principal,
                versions=context.versions.versions,
                deps=deps,
                evidence_lookup=lambda _u, _ids: (),
                doc_type_lookup=lambda _u, _ids: {},
                trace_id=ctx.identity.trace_id,
                run_id=str(ctx.identity.run_id),
                as_of=ctx.query_context.as_of,
            ),
            check_bindings,
            final_config,
        )

    provider = StaticKeyProvider({"PUBLIC-test-key": b"K" * 32}, "PUBLIC-test-key")
    runtime = AgentRuntime(
        connection=connection,
        gateway=gateway,
        provider=provider,
        database_binding=binding,
        config=PlannerConfig(model_id="gpt-6-sol", max_output_tokens=512, timeout_s=20),
        limits=limits or ExecutionLimits(token_limit=12000, cost_limit_usd=0.6, timeout_s=125),
        resources=resources,
        lease_s=lease_s,
        retention_days=90,
    )
    state.update(
        runtime=runtime, run=run, connection=connection, provider=provider, binding=binding, resources=resources
    )
    return state
