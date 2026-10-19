"""PUBLIC clarification setup: real production composition, fake models/retrieval only."""

import math
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import psycopg

from medops.application.agent_continuation import ClarificationPolicy, ContinuationAuthorization, ContinueAgent
from medops.bootstrap.agent_continuation import production_agent_continuation
from medops.bootstrap.agent_services import bind_new_agent_context, production_agent_runtime
from medops.infrastructure.identity import pseudonym
from tests.support.agent_audit import audit_runtime
from tests.support.agent_terminal import PublicRetrievalAgent, terminal_case
from tests.support.api_runtime import ISSUER_OBJ
from tests.support.harness import FakeRetrieval
from tests.support.identity import PSEUDONYM_KEY


def simulated_billing(gateway):
    """Synthetic receipt amount only. Still entirely offline, actual hosted cost $0."""
    original = gateway.complete

    def complete(request):
        return original(request).model_copy(update={"cost_usd": 0.001})

    gateway.complete = complete
    return gateway


class StoredRetrieval:
    def __init__(self, case):
        self.case = case

    def build(self, _unused, user, context, _routed, _meter, *, connection_for_user):
        from medops.retrieval.recheck import recheck_candidates

        with connection_for_user(user) as conn:
            fresh = recheck_candidates(
                conn, (self.case["chunk"],), as_of=context.as_of, allow_historical=context.historical_requested
            )
        return FakeRetrieval(*fresh.evidence)

    def reranker_for(self, output):
        return SimpleNamespace(score=lambda q, texts: [1.0] * len(texts))


def principal(db, *, dept="PV", scopes=None):
    sub = "PUBLIC-clarification-" + uuid4().hex
    pid = pseudonym(sub, PSEUDONYM_KEY)
    with psycopg.connect(db["owner"]) as conn:
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values (%s,%s,array[]::text[],%s,'PUBLIC-clarification')",
            (pid, dept, scopes if scopes is not None else [dept + ":read"]),
        )
    return pid, "Bearer " + ISSUER_OBJ.token(sub)


def clarification_case(
    db,
    *,
    max_continuations=2,
    case_limit=2000000,
    batch_limit=1200000,
    max_executions=2,
    owner_state=None,
    ttl_from_now=None,
):
    case, source_fake = terminal_case(db, "clarify")
    runtime, _, _ = audit_runtime(case)
    runtime.versions = case["context"].versions.versions
    runtime._retrieval_services = StoredRetrieval(case)
    runtime.gateway = simulated_billing(source_fake)
    pid, authorization = principal(db) if owner_state is None else (owner_state["pid"], owner_state["authorization"])
    with runtime.connection() as conn:
        user = runtime.resolve_user(conn, pid)
    context = case["context"].model_copy(update={"principal": user, "clarifiable_fields": ("source_version", "event")})
    config = case["runtime"].config
    final = case["runtime"].resources(case["context"], None).final_config
    context = bind_new_agent_context(
        runtime, context, config=config, final_config=final, database_binding=case["binding"]
    )
    executor = production_agent_runtime(
        runtime, context, config=config, final_config=final, database_binding=case["binding"], lease_s=10
    )
    with executor.start(executor.new_run(context)) as execution:
        source = execution.execute()
    assert source.run.status == "awaiting_clarification", (source.material.reason, len(source_fake.calls))
    fake = simulated_billing(PublicRetrievalAgent())
    runtime.gateway = fake
    service = production_agent_continuation(
        runtime,
        config=config,
        final_config=final,
        database_binding=case["binding"],
        rubric_sha256=context.versions.rubric_sha256,
        lease_s=10,
    )
    ttl = (
        3600
        if ttl_from_now is None
        else math.ceil((datetime.now(UTC) - source.run.started_at).total_seconds()) + ttl_from_now
    )
    policy = ClarificationPolicy(ttl_seconds=ttl, max_continuations=max_continuations, cost_limit_microusd=case_limit)
    business_case = service.open_case(context.identity.run_id, policy, authorization=authorization)
    grant = ContinuationAuthorization(
        batch_id=uuid4(),
        approval_sha256="a" * 64,
        case_ids=(context.identity.case_id,),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        max_executions=max_executions,
        cost_limit_microusd=batch_limit,
    )
    service.authorize(grant, authorization=authorization)
    command = ContinueAgent(
        command_id=uuid4(),
        batch_id=grant.batch_id,
        expected_revision=business_case.revision,
        answers=({"field": "source_version", "value": "PUBLIC v1"},),
    )
    return dict(
        case=case,
        runtime=runtime,
        source=source,
        source_context=context,
        source_fake=source_fake,
        executor=executor,
        service=service,
        authorization=authorization,
        grant=grant,
        policy=policy,
        command=command,
        fake=fake,
        business_case=business_case,
        pid=pid,
        db=db,
    )


def continue_case(state, command=None):
    return state["service"].continue_case(
        state["source_context"].identity.run_id,
        state["command"] if command is None else command,
        authorization=state["authorization"],
    )
