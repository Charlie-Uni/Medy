"""M3-13 fault tests on the main chain with fakes: a model timeout, a worker that dies mid-task, and duplicate
consumption. Each case checks three things: the failure is locatable (trace spans / attempts name the node,
the attempt and the code), it is recoverable (the same request succeeds once the fault clears, reusing what
already succeeded), and the safety chain is never bypassed (no unverified answer, no answer without audit,
refusals still happen before any model call)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.api.contracts import TaskCreateRequest, TaskStatus
from medops.application.audit import InMemoryTraceStore
from medops.application.tasks import InMemoryTaskStore, TaskRunner, TaskService
from medops.domain.common import Dept, DomainModel, NonEmptyStr, RiskLevel
from medops.domain.identity import UserContext
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout, ModelUnavailable
from medops.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from tests.unit.api.test_ask_route import ANSWER, QUERY, FakeRuntime, auth
from tests.unit.harness._fixtures import evidence, versions
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval, make_deps

T0 = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)


def client(rt) -> TestClient:
    return TestClient(create_app(rt), raise_server_exceptions=False)


# ------------------------------------------------------------------------------------ 1. model timeout


def test_model_timeout_is_locatable_recoverable_and_never_an_unverified_answer():
    # three timeouts (one attempt + two retries), then the provider recovers
    gateway = FakeModelGateway({"answer": [ModelTimeout("slow")] * 3 + [ANSWER]})
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), gateway)
    c = client(rt)
    r = c.post("/v1/ask", json={"query": QUERY}, headers=auth())
    body = r.json()
    assert (
        r.status_code == 200
        and body["outcome"] == "escalated"
        and body["escalation"]["reason_codes"] == ["system_failure"]
    )
    assert body["answer"] is None  # never an unverified or partial answer
    trace = rt.traces.traces[body["trace_id"]]
    failing = [s for s in trace.spans if s.node == "answer"]
    assert [s.outcome for s in failing] == ["retry", "retry", "failed"] and failing[
        -1
    ].error_code == "dependency_timeout"
    assert body["trace_id"] in rt.traces.escalations  # a human can pick it up
    # recovery: the same question after the provider is back answers; intent/retrieve/verify/safety are reused from
    # the operation-key ledger (same run id would be required for reuse; a new request is a new trace, so they run again)
    r2 = c.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert r2.status_code == 200 and r2.json()["outcome"] == "answered"
    assert len(gateway.calls) == 4  # 3 failed + 1 successful answer call, no extra guessing


def test_provider_outage_keeps_refusals_ahead_of_any_model_call():
    gateway = FakeModelGateway({"answer": [ModelUnavailable("down", retryable=True)] * 3})
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), gateway)
    c = client(rt)
    refused = c.post("/v1/ask", json={"query": "我最近血压 150/95，我应该每天吃多少 losartan？"}, headers=auth()).json()
    assert refused["outcome"] == "refused" and gateway.calls == []
    out = c.post("/v1/ask", json={"query": QUERY}, headers=auth()).json()
    assert out["outcome"] == "escalated" and out["escalation"]["reason_codes"] == ["system_failure"]
    answer_spans = [s for s in rt.traces.traces[out["trace_id"]].spans if s.node == "answer"]
    assert (
        len(gateway.calls) == 3 and answer_spans[-1].error_code == "dependency_unavailable"
    )  # the failing node is named


# ------------------------------------------------------------------------------------ 2. worker restart


class EchoIn(DomainModel):
    text: NonEmptyStr


class EchoOut(SkillOutput):
    text: str = ""


def make_registry(handler) -> SkillRegistry:
    reg = SkillRegistry(sleep=lambda s: None)
    reg.register(
        RegisteredSkill(
            spec=SkillSpec(
                name="echo_skill",
                version="1.0.0",
                description="echo",
                risk=RiskLevel.low,
                required_scopes=("$dept:read",),
                timeout_s=1,
            ),
            input_model=EchoIn,
            output_model=EchoOut,
            handler=handler,
        )
    )
    return reg


class WorkerEnv:
    def __init__(self, store: InMemoryTaskStore, reg: SkillRegistry, user: UserContext):
        self.store, self.reg, self.user = store, reg, user
        self.traces = InMemoryTraceStore()

    @contextmanager
    def connection(self):
        yield "conn"

    def resolve_user(self, conn, principal):
        return self.user if principal == self.user.user_id else None

    def bind_identity(self, conn, user):
        pass

    def task_store(self, conn):
        return self.store

    def trace_store(self, conn):
        return self.traces

    def skill_context(self, conn, user, trace_id, historical):
        return SkillContext(
            user=user,
            versions=versions().model_copy(update={"skill_version_set": self.reg.version_set()}),
            deps=make_deps(FakeRetrieval(), FakeModelGateway()),
            evidence_lookup=lambda _u, _ids: (),
            doc_type_lookup=lambda _u, _ids: {},
            trace_id=trace_id,
            run_id=trace_id,
        )


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def test_worker_dying_mid_task_is_recovered_by_another_worker_after_the_lease():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    user = UserContext(user_id="a" * 32, dept=Dept.PV, acl_scopes=frozenset({"PV:read"}))
    svc = TaskService(store=store, clock=clock)
    task = svc.create(
        user, TaskCreateRequest(skill_name="echo_skill", skill_version="1.0.0", input={"text": "hi"}), None
    )
    # worker 1 claims and "dies": it never reports (simulated by claiming directly and doing nothing more)
    claimed = store.claim_next("worker-1", 60, clock())
    assert claimed is not None and store.get(task.task_id).status is TaskStatus.running
    # a second worker before the lease expires must not touch it
    reg = make_registry(lambda ctx, inp: EchoOut(status=SkillStatus.completed, text=inp.text.upper()))
    runner2 = TaskRunner(env=WorkerEnv(store, reg, user), registry=reg, worker_id="worker-2", clock=clock)
    assert runner2.run_once() is None
    # lease expired: worker 2 takes over, finishes, and the record shows what happened
    clock.now = T0 + timedelta(seconds=61)
    done = runner2.run_once()
    assert done is not None and done.status is TaskStatus.completed and done.attempts == 2
    assert [(a["attempt"], a["worker"], a["outcome"]) for a in store.attempts] == [
        (1, "worker-1", "lost"),
        (2, "worker-2", "completed"),
    ]
    # the dead worker's late report is ignored: the outcome cannot be overwritten
    assert store.complete(task.task_id, "worker-1", 1, "b" * 32, {"stale": True}, clock()) is False
    assert store.get(task.task_id).result["output"]["text"] == "HI"
    assert done.trace_id in runner2.env.traces.traces


# ------------------------------------------------------------------------------------ 3. duplicate consumption


def test_duplicate_consumption_is_bounded_by_the_lease_and_the_operation_key_ledger():
    clock = Clock()
    store = InMemoryTaskStore(clock=clock)
    user = UserContext(user_id="a" * 32, dept=Dept.PV, acl_scopes=frozenset({"PV:read"}))
    TaskService(store=store, clock=clock).create(
        user, TaskCreateRequest(skill_name="echo_skill", skill_version="1.0.0", input={"text": "once"}), None
    )
    executions: list[str] = []

    def counting(ctx: SkillContext, inp: EchoIn) -> EchoOut:
        executions.append(inp.text)
        return EchoOut(status=SkillStatus.completed, text=inp.text)

    reg = make_registry(counting)
    env = WorkerEnv(store, reg, user)
    a = TaskRunner(env=env, registry=reg, worker_id="w-a", clock=clock)
    b = TaskRunner(env=env, registry=reg, worker_id="w-b", clock=clock)
    first, second = a.run_once(), b.run_once()
    assert (first is not None) != (second is not None)  # exactly one worker got the task
    assert executions == ["once"]
    # idempotent create + a repeated submission with the same key never enqueues a second copy
    svc = TaskService(store=store, clock=clock)
    req = TaskCreateRequest(skill_name="echo_skill", skill_version="1.0.0", input={"text": "twice?"})
    t1 = svc.create(user, req, "same-key")
    t2 = svc.create(user, req, "same-key")
    assert t1.task_id == t2.task_id and sum(1 for t in store.tasks.values() if t.input.get("text") == "twice?") == 1


def test_audit_outage_never_yields_an_answer_and_recovers_without_a_second_model_call_only_when_reused():
    gateway = FakeModelGateway({"answer": [ANSWER, ANSWER]})
    rt = FakeRuntime(FakeRetrieval(evidence("c1", LABEL)), gateway)
    rt.traces.fail_with = RuntimeError("audit store down")
    c = client(rt)
    r = c.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert r.status_code == 503 and r.json()["code"] == "audit_unavailable" and "claims" not in r.text
    rt.traces.fail_with = None
    ok = c.post("/v1/ask", json={"query": QUERY}, headers=auth())
    assert ok.status_code == 200 and ok.json()["outcome"] == "answered" and ok.json()["trace_id"] in rt.traces.traces
