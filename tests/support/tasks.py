"""Shared tasks test support; no collected test cases."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

from medops.application.audit import InMemoryTraceStore
from medops.application.contracts import TaskCreateRequest
from medops.application.tasks import InMemoryTaskStore
from medops.domain.common import Dept, DomainModel, NonEmptyStr, RiskLevel
from medops.domain.identity import UserContext
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from tests.support.harness import FakeRetrieval, make_deps
from tests.support.harness_data import versions

T0 = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now


def user(dept=Dept.PV, uid="p" * 32) -> UserContext:
    return UserContext(user_id=uid, dept=dept, acl_scopes=frozenset({f"{dept.value}:read"}))


def req(text="hi") -> TaskCreateRequest:
    return TaskCreateRequest(skill_name="echo_skill", skill_version="1.0.0", input={"text": text})


class EchoIn(DomainModel):
    text: NonEmptyStr


class EchoOut(SkillOutput):
    text: str = ""


def echo(ctx: SkillContext, inp: EchoIn) -> EchoOut:
    return EchoOut(status=SkillStatus.completed, text=inp.text.upper())


def registry(handler=echo) -> SkillRegistry:
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


class FakeEnv:
    def __init__(self, store: InMemoryTaskStore, reg: SkillRegistry, principals: dict[str, UserContext]):
        self.store, self.reg, self.principals = store, reg, principals
        self.traces = InMemoryTraceStore()

    @contextmanager
    def connection(self):
        yield "conn"

    def resolve_user(self, conn, principal):
        return self.principals.get(principal)

    def bind_identity(self, conn, user):
        pass

    def validate_final_output(self, conn, user, evidence, context, *, authorization=None, lookups=()):
        from medops.infrastructure.db.final_output import require_same_user

        require_same_user(user, self.resolve_user(conn, user.user_id))

    def task_store(self, conn):
        return self.store

    def trace_store(self, conn):
        return self.traces

    def payload_writer(self, conn):
        return None

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
