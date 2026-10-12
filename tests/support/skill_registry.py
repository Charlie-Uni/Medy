"""Shared skill registry test support; no collected test cases."""

from __future__ import annotations

from medops.domain.common import DomainModel, NonEmptyStr, RiskLevel
from medops.domain.identity import UserContext
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from tests.support.harness import FakeRetrieval, make_deps
from tests.support.harness_data import user, versions


class EchoIn(DomainModel):
    text: NonEmptyStr


class EchoOut(SkillOutput):
    text: str = ""


def echo(ctx: SkillContext, inp: EchoIn) -> EchoOut:
    return EchoOut(status=SkillStatus.completed, text=inp.text)


def spec(name="echo_skill", **kw) -> SkillSpec:
    base = dict(
        name=name,
        version="1.0.0",
        description="echo",
        risk=RiskLevel.low,
        required_scopes=("$dept:read",),
        timeout_s=1,
    )
    base.update(kw)
    return SkillSpec(**base)


def entry(handler=echo, **kw) -> RegisteredSkill:
    return RegisteredSkill(spec=spec(**kw), input_model=EchoIn, output_model=EchoOut, handler=handler)


def registry(*entries: RegisteredSkill) -> SkillRegistry:
    reg = SkillRegistry(sleep=lambda s: None)
    for e in entries:
        reg.register(e)
    return reg


def context(reg: SkillRegistry, u: UserContext | None = None) -> SkillContext:
    vs = versions().model_copy(update={"skill_version_set": reg.version_set()})
    return SkillContext(
        user=u or user(),
        versions=vs,
        deps=make_deps(FakeRetrieval(), FakeModelGateway()),
        evidence_lookup=lambda _u, _ids: (),
        doc_type_lookup=lambda _u, _ids: {},
        trace_id="a" * 32,
        run_id="a" * 32,
    )
