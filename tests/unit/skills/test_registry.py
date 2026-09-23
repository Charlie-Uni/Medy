"""Skill Registry enforcement (M2-11, INV-AUTH-03): scopes before anything else, schema, version set, timeout and
retry policy, output contract, safety layer 3 and parallel execution only for parallel_safe skills."""

from __future__ import annotations

import threading
import time

import pytest
from pydantic import ValidationError

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept, DomainModel, NonEmptyStr, ReasonCode, RiskLevel
from medops.domain.identity import UserContext
from medops.domain.safety import SafetyDecision
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.registry import RegisteredSkill, SkillContext, SkillRegistry, SkillRequest
from tests.unit.harness._fixtures import user, versions
from tests.unit.harness.test_run_ask import FakeRetrieval, make_deps


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


def test_execute_checks_scopes_and_schema_then_returns_the_typed_output_with_an_attempt_record():
    reg = registry(entry())
    run = reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg))
    assert isinstance(run.output, EchoOut) and run.output.text == "hi" and run.output.status is SkillStatus.completed
    assert [a.outcome for a in run.attempts] == ["ok"] and run.attempts[0].node == "skill:echo_skill"
    assert len(run.operation_key) == 64 and run.safety.decision is SafetyDecision.allow
    assert reg.version_set() == ("echo_skill@1.0.0",)
    assert reg.describe("echo_skill", "1.0.0")["input_schema"]["required"] == ["text"]


def test_default_deny_and_department_placeholder_resolution():
    reg = registry(entry())
    no_scope = UserContext(user_id="u1", dept=Dept.PV, acl_scopes=frozenset())
    with pytest.raises(BusinessError) as exc:
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg, no_scope))
    assert exc.value.code is ErrorCode.forbidden and "PV:read" in (exc.value.detail or "")
    other_dept = UserContext(user_id="u2", dept=Dept.PV, acl_scopes=frozenset({"MA:read"}))
    with pytest.raises(BusinessError):
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg, other_dept))
    ma = UserContext(user_id="u3", dept=Dept.MA, acl_scopes=frozenset({"MA:read"}))
    assert (
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg, ma)).output.status
        is SkillStatus.completed
    )


def test_scope_check_precedes_schema_validation():
    reg = registry(entry())
    no_scope = UserContext(user_id="u1", dept=Dept.PV, acl_scopes=frozenset())
    with pytest.raises(BusinessError) as exc:
        reg.execute("echo_skill", "1.0.0", {"bogus": 1}, context=context(reg, no_scope))
    assert exc.value.code is ErrorCode.forbidden


@pytest.mark.parametrize("raw", [{"text": ""}, {"text": "x", "extra": 1}, {}, "not an object"])
def test_schema_violations_are_rejected_before_the_handler_runs(raw):
    calls = []

    def spy(ctx, inp):
        calls.append(inp)
        return echo(ctx, inp)

    reg = registry(entry(handler=spy))
    with pytest.raises(BusinessError) as exc:
        reg.execute("echo_skill", "1.0.0", raw, context=context(reg))
    assert exc.value.code is ErrorCode.schema_violation and calls == []


def test_unknown_skill_or_version_is_not_found():
    reg = registry(entry())
    with pytest.raises(BusinessError) as exc:
        reg.execute("echo_skill", "2.0.0", {"text": "hi"}, context=context(reg))
    assert exc.value.code is ErrorCode.not_found


def test_run_version_set_must_record_the_skill():
    reg = registry(entry())
    ctx = context(reg)
    stale = SkillContext(**{**ctx.__dict__, "versions": versions()})
    with pytest.raises(InfrastructureError) as exc:
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=stale)
    assert exc.value.code is ErrorCode.internal_error


def test_timeout_escalates_as_system_failure_and_retries_only_idempotent_skills():
    def slow(ctx, inp):
        time.sleep(0.3)
        return echo(ctx, inp)

    reg = registry(entry(handler=slow, timeout_s=0.05))
    run = reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg))
    assert run.output.status is SkillStatus.escalated and run.output.reason_codes == (ReasonCode.system_failure,)
    assert [a.outcome for a in run.attempts] == ["failed"] and type(run.output) is SkillOutput

    reg2 = registry(entry(handler=slow, timeout_s=0.05, idempotent=True))
    run2 = reg2.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg2))
    assert [a.outcome for a in run2.attempts] == ["timeout", "timeout", "failed"]


def test_output_contract_violation_is_an_internal_error():
    reg = registry(entry(handler=lambda ctx, inp: SkillOutput(status=SkillStatus.completed)))
    with pytest.raises(InfrastructureError) as exc:
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg))
    assert exc.value.code is ErrorCode.internal_error


def test_output_safety_layer_replaces_advice_with_a_bare_escalation():
    reg = registry(entry())
    run = reg.execute("echo_skill", "1.0.0", {"text": "您应该每天服用 100 mg"}, context=context(reg))
    assert run.safety.decision is SafetyDecision.refuse
    assert type(run.output) is SkillOutput and run.output.status is SkillStatus.escalated
    assert run.output.reason_codes == (ReasonCode.high_risk_medical,) and run.output.rendered_texts() == ()


def test_business_errors_raised_by_a_handler_reach_the_caller():
    def bad(ctx, inp):
        raise BusinessError(ErrorCode.invalid_request, "historical evidence requires as_of")

    reg = registry(entry(handler=bad))
    with pytest.raises(BusinessError) as exc:
        reg.execute("echo_skill", "1.0.0", {"text": "hi"}, context=context(reg))
    assert exc.value.code is ErrorCode.invalid_request


def test_execute_many_runs_concurrently_only_parallel_safe_skills_and_keeps_request_order():
    seen: dict[str, list[str]] = {"par": [], "seq": []}
    lock = threading.Lock()

    def par(ctx, inp):
        with lock:
            seen["par"].append(threading.current_thread().name)
        time.sleep(0.05)
        return EchoOut(status=SkillStatus.completed, text="par:" + inp.text)

    def seq(ctx, inp):
        with lock:
            seen["seq"].append(threading.current_thread().name)
        return EchoOut(status=SkillStatus.completed, text="seq:" + inp.text)

    reg = registry(
        entry(handler=par, name="par_skill", parallel_safe=True),
        entry(handler=seq, name="seq_skill", parallel_safe=False),
    )
    requests = [
        SkillRequest("par_skill", "1.0.0", {"text": "1"}),
        SkillRequest("seq_skill", "1.0.0", {"text": "2"}),
        SkillRequest("par_skill", "1.0.0", {"text": "3"}),
        SkillRequest("seq_skill", "1.0.0", {"bogus": 4}),
    ]
    results = reg.execute_many(requests, context=context(reg))
    assert [getattr(r, "output", None) and r.output.text for r in results[:3]] == ["par:1", "seq:2", "par:3"]
    assert isinstance(results[3], BusinessError) and results[3].code is ErrorCode.schema_violation
    # the handler runs inside run_node's worker thread; parallel skills get distinct outer threads
    assert len(seen["par"]) == 2 and len(seen["seq"]) == 1  # the fourth request failed schema validation


def test_registration_rejects_duplicates_and_specs_require_a_scope_and_bounded_timeout():
    reg = registry(entry())
    with pytest.raises(ValueError):
        reg.register(entry())
    with pytest.raises(ValidationError):
        spec(required_scopes=())
    with pytest.raises(ValidationError):
        spec(timeout_s=500)
    with pytest.raises(ValidationError):
        spec(required_scopes=("everyone:read",))
    with pytest.raises(ValidationError):
        SkillOutput(status=SkillStatus.escalated)
