"""Shared skill task test support; no collected test cases."""

from dataclasses import replace

from medops.application.contracts import TaskCreateRequest
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.tasks import InMemoryTaskStore, TaskRunner, TaskService
from medops.domain.common import Dept
from medops.skills.catalog import default_registry
from tests.support.payloads import PROVIDER, MemoryPayloads
from tests.support.skill_matrix import SKILLS, context, scripted
from tests.support.tasks import Clock, FakeEnv, user


class SkillEnv(FakeEnv):
    def __init__(self, name, *, overrides=None):
        self.clock = Clock()
        self.name, self.spec = name, SKILLS[name]
        self.gateway = scripted(self.spec, **(overrides or {}))
        reg = default_registry(sleep=lambda _s: None)
        self.u = user(dept=Dept(self.spec["dept"]))
        super().__init__(InMemoryTaskStore(clock=self.clock), reg, {self.u.user_id: self.u})
        self.payloads = MemoryPayloads()

    def skill_context(self, conn, selected_user, trace_id, historical):
        ctx = context(self.reg, self.spec, gateway=self.gateway, u=selected_user)
        return replace(ctx, trace_id=trace_id, run_id=trace_id)

    def payload_writer(self, conn):
        return PayloadWriter(self.payloads, PROVIDER)

    def run(self):
        TaskService(self.store, clock=self.clock).create(
            self.u, TaskCreateRequest(skill_name=self.name, skill_version="1.0.0", input=self.spec["input"]), None
        )
        return TaskRunner(self, self.reg, worker_id="w1", clock=self.clock).run_once()

    def decrypted(self, trace_id):
        read = PayloadReader(self.payloads, PROVIDER).read(self.u, trace_id, "test incident review")
        return {item.kind: item.payload for item in read.items}
