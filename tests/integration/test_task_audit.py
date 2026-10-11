"""ARCH-06 on PostgreSQL: task, spans, escalation and encrypted bodies commit together."""

from contextlib import contextmanager

import psycopg
import pytest

from medops.application.contracts import TaskCreateRequest, TaskStatus
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.tasks import TaskRunner, TaskService
from medops.core.errors import InfrastructureError
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.payloads import PgPayloadStore
from medops.infrastructure.db.tasks import PgTaskStore
from medops.infrastructure.llm.gateway import ModelTimeout
from tests.integration.lexical_adapter_suite import make_database
from tests.unit.api.test_payload_route import PROVIDER
from tests.unit.application.test_task_audit import SkillEnv


@pytest.fixture
def db(admin_dsn):
    yield from make_database(admin_dsn)


class PgEnv(SkillEnv):
    def __init__(self, db, *, fault=None, persistent=False, overrides=None):
        super().__init__("protocol_deviation", overrides=overrides)
        self.u = self.u.model_copy(update={"user_id": "b" * 32})
        self.principals = {self.u.user_id: self.u}
        self.db, self.fault, self.persistent = db, fault, persistent
        self.tripped = False

    def trip(self, fault):
        if self.fault == fault and (self.persistent or not self.tripped):
            self.tripped = True
            raise RuntimeError("private storage or key detail")

    @contextmanager
    def connection(self):
        with psycopg.connect(self.db["users"]["app"]) as conn:
            yield conn

    def task_store(self, conn):
        return PgTaskStore(conn)

    def trace_store(self, conn):
        env = self

        class Store(PgTraceStore):
            def record(self, trace, escalation):
                super().record(trace, escalation)
                env.trip("trace")  # failure after real inserts, not before them

        return Store(conn)

    def payload_writer(self, conn):
        env = self

        class Store(PgPayloadStore):
            def put(self, *args, **kwargs):
                value = super().put(*args, **kwargs)
                env.trip("payload")  # failure after partial ciphertext insertion
                return value

        class Provider:
            def current(self):
                env.trip("seal")
                return PROVIDER.current()

            def key(self, version):
                return PROVIDER.key(version)

        return PayloadWriter(Store(conn), Provider())

    def create(self):
        with self.connection() as conn:
            return TaskService(PgTaskStore(conn)).create(
                self.u, TaskCreateRequest(skill_name=self.name, skill_version="1.0.0", input=self.spec["input"]), None
            )


def test_real_retries_persist_unique_spans_and_access_logged_ciphertext(db):
    env = PgEnv(db, overrides={"skill:protocol_deviation": [ModelTimeout()] * 3})
    env.create()
    done = TaskRunner(env, env.reg, worker_id="w1").run_once().record
    assert done.status is TaskStatus.completed and done.result["status"] == "escalated"
    with psycopg.connect(db["users"]["admin"]) as conn:
        row = conn.execute(
            "select evidence_chunk_ids,cited_chunk_ids from traces where trace_id=%s", (done.trace_id,)
        ).fetchone()
        assert row == (["c1"], [])
        spans = conn.execute("select node,attempt from trace_spans where trace_id=%s", (done.trace_id,)).fetchall()
        assert sorted(a for n, a in spans if n == "retrieve") == [1, 2, 3]
        assert len(spans) == len(set(spans))
        assert conn.execute("select count(*) from escalations where trace_id=%s", (done.trace_id,)).fetchone()[0] == 1
    with psycopg.connect(db["users"]["restricted"]) as conn:
        store = PgPayloadStore(conn)
        rows = store.list(done.trace_id)
        assert len(rows) == 3 and all(b"observation" not in r["sealed"].ciphertext for r in rows)
        payload = PayloadReader(store, PROVIDER).read(env.u, done.trace_id, "incident review ARCH06")
        model = next(p.payload for p in payload.items if p.kind == "model_output")
        assert sum(e["kind"] == "harness" for e in model["events"]) == 3
        assert model["model_call_audit_complete"]
        assert len(model["model_calls"]) == len(env.gateway.calls)
        assert all(c["receipt"]["call"]["trace_id"] == done.trace_id for c in model["model_calls"])
        assert all(c["request"]["messages"] for c in model["model_calls"])
        inputs = next(p.payload for p in payload.items if p.kind == "input")
        assert inputs["conditions"]["artifacts"]["source"]["sha256"]
    with psycopg.connect(db["users"]["admin"]) as conn:
        assert conn.execute(
            "select purpose from payload_access_log where trace_id=%s", (done.trace_id,)
        ).fetchall() == [("incident review ARCH06",)]


@pytest.mark.parametrize("fault", ["trace", "seal", "payload"])
def test_audit_fault_rolls_back_completed_result_and_reports_failure_without_rerunning_model(db, fault):
    env = PgEnv(db, fault=fault)
    env.create()
    done = TaskRunner(env, env.reg, worker_id="w1").run_once().record
    assert env.tripped and done.status is TaskStatus.failed and done.result is None
    assert done.error["code"] == "audit_unavailable"
    assert len(env.gateway.calls) == 3  # answer + structured generation + final judgment, no paid retry
    with psycopg.connect(db["users"]["admin"]) as conn:
        trace = conn.execute(
            "select outcome,cited_chunk_ids from traces where trace_id=%s", (done.trace_id,)
        ).fetchall()
        assert trace == [("escalated", [])]
    with psycopg.connect(db["users"]["restricted"]) as conn:
        payloads = PgPayloadStore(conn).list(done.trace_id)
        assert len(payloads) == 3  # rolled-back first partial write is gone


def test_persistent_audit_failure_releases_no_result_and_leaves_lease_for_recovery(db):
    env = PgEnv(db, fault="payload", persistent=True)
    task = env.create()
    with pytest.raises(InfrastructureError) as exc:
        TaskRunner(env, env.reg, worker_id="w1").run_once()
    assert exc.value.code.value == "audit_unavailable" and len(env.gateway.calls) == 3
    with env.connection() as conn:
        current = PgTaskStore(conn).get(task.task_id)
        assert current.status is TaskStatus.running and current.result is None and current.trace_id is None
        assert conn.execute("select count(*) from traces where task_id=%s", (task.task_id,)).fetchone()[0] == 0
    with psycopg.connect(db["users"]["restricted"]) as conn:
        assert conn.execute("select count(*) from trace_payloads").fetchone()[0] == 0
