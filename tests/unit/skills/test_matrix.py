"""M5-02 test matrix (record 88): the five delivered Skills × the cross-cutting dimensions, through the Registry with
fakes — permission is checked before any model call, a schema violation never reaches the handler, an empty evidence
set ends in `insufficient_evidence` without a model call, a provider fault ends in a bounded `system_failure`, and no
output ever carries individual medical advice. Functional happy paths are the per-skill tests
(test_label_query, test_citation_verification, test_risk_skills) and the real smoke runs
(`evals/harness/runs/2026-09-23-skill-smoke-v1` / `-v2`)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import DocStatus, ReasonCode
from medops.domain.query import QueryContext
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.skills.catalog import default_registry
from tests.support.harness import FakeRetrieval
from tests.support.harness_data import evidence
from tests.support.skill_matrix import ADVICE, SKILLS, context, scripted, user

NAMES = tuple(SKILLS)


@pytest.mark.parametrize("name", ["label_query", "citation_verification", "off_label_check", "protocol_deviation"])
def test_all_document_skills_preserve_a_notice_for_archived_evidence(name):
    reg = default_registry(sleep=lambda _s: None)
    spec = SKILLS[name]
    archived = evidence("c1", spec["evidence"][0], status=DocStatus.archived, historical=True)
    port = FakeRetrieval(archived)
    ctx = context(reg, spec, gateway=scripted(spec), retrieval=port, lookup=lambda _u, _ids: (archived,))
    selected = QueryContext(as_of=date(2026, 6, 1), historical_requested=True)
    ctx = replace(ctx, as_of=selected.as_of, deps=replace(ctx.deps, as_of=selected.as_of, query_context=selected))
    output = reg.execute(name, "1.0.0", spec["input"], context=ctx).output
    assert output.status is SkillStatus.completed and output.historical_notice is True
    assert output.model_dump(mode="json")["historical_notice"] is True


@pytest.mark.parametrize("name", NAMES)
def test_permission_is_checked_before_any_model_call(name):
    """Right department, wrong scope -> forbidden; the gateway has no script, so any model call would blow up."""
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    c = context(reg, spec, gateway=FakeModelGateway({}), u=user(spec["dept"], {f"{spec['dept']}:write"}))
    with pytest.raises(BusinessError) as info:
        reg.execute(name, "1.0.0", spec["input"], context=c)
    assert info.value.code is ErrorCode.forbidden


@pytest.mark.parametrize("name", ("ae_extraction", "off_label_check", "protocol_deviation"))
def test_fixed_department_skills_refuse_other_departments(name):
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    other = {"PV": "MA", "MA": "CO", "CO": "PV"}[spec["dept"]]
    c = context(reg, spec, gateway=FakeModelGateway({}), u=user(other))
    with pytest.raises(BusinessError) as info:
        reg.execute(name, "1.0.0", spec["input"], context=c)
    assert info.value.code is ErrorCode.forbidden


@pytest.mark.parametrize("name", NAMES)
def test_schema_violations_never_reach_the_handler(name):
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    with pytest.raises(BusinessError) as info:
        reg.execute(name, "1.0.0", {}, context=context(reg, spec, gateway=FakeModelGateway({})))
    assert info.value.code is ErrorCode.schema_violation


@pytest.mark.parametrize("name", ("label_query", "off_label_check", "protocol_deviation"))
def test_no_evidence_ends_in_insufficient_evidence_without_a_model_call(name):
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    run = reg.execute(
        name,
        "1.0.0",
        spec["input"],
        context=context(reg, spec, gateway=FakeModelGateway({}), retrieval=FakeRetrieval()),
    )
    assert run.output.status is not SkillStatus.completed
    assert (
        run.output.status is SkillStatus.insufficient_evidence
        or ReasonCode.insufficient_evidence in run.output.reason_codes
    )
    assert ReasonCode.system_failure not in run.output.reason_codes  # nothing tried to call the (unscripted) model


def test_ae_extraction_without_grounded_elements_is_insufficient_evidence():
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS["ae_extraction"]
    gateway = scripted(spec, **{"skill:ae_extraction": [{"elements": []}]})
    run = reg.execute("ae_extraction", "1.0.0", spec["input"], context=context(reg, spec, gateway=gateway))
    assert run.output.status is SkillStatus.insufficient_evidence


@pytest.mark.parametrize("name", NAMES)
def test_provider_fault_is_a_bounded_system_failure(name):
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    faults = [ModelTimeout("provider timeout") for _ in range(6)]
    if name == "citation_verification":

        def broken_lookup(_u, _ids):
            raise InfrastructureError(ErrorCode.dependency_unavailable, detail="evidence store down", retryable=True)

        c = context(reg, spec, gateway=FakeModelGateway({}), lookup=broken_lookup)
    elif name == "label_query":
        c = context(reg, spec, gateway=FakeModelGateway({"answer": faults}))
    else:
        c = context(reg, spec, gateway=scripted(spec, **{spec["purpose"]: faults}))
    run = reg.execute(name, "1.0.0", spec["input"], context=c)
    assert run.output.status is SkillStatus.escalated and ReasonCode.system_failure in run.output.reason_codes
    assert 1 <= len(run.attempts) <= 3  # bounded retries (idempotent skills retry at most twice)
    assert all(ADVICE not in t for t in run.output.rendered_texts())
    assert run.output.rendered_texts() == () or all(
        t in ("undetermined", "none", "") or "不构成" in t for t in run.output.rendered_texts()
    )  # a failed run never carries a finding, only the fixed disclaimer


@pytest.mark.parametrize("name", NAMES)
def test_no_output_carries_individual_advice(name):
    """Advice planted in the model reply (or, for the two skills without a free-text reply, in the answer / claim
    text) never reaches the caller: the output is replaced by a bare escalation or the text is gone."""
    reg = default_registry(sleep=lambda s: None)
    spec = SKILLS[name]
    if name == "label_query":
        gateway = FakeModelGateway({"answer": [{"claims": [{"text": ADVICE, "citation_chunk_ids": ["c1"]}]}] * 2})
        raw = spec["input"]
    elif name == "citation_verification":
        gateway = FakeModelGateway({})
        raw = {"claims": [{"text": ADVICE, "citation_chunk_ids": ["c1"]}]}
    else:
        gateway = scripted(spec, **{spec["purpose"]: [spec["advice_reply"]]})
        raw = spec["input"]
    run = reg.execute(name, "1.0.0", raw, context=context(reg, spec, gateway=gateway))
    assert all(ADVICE not in t for t in run.output.rendered_texts())
    if run.output.status is SkillStatus.escalated:
        assert run.output.rendered_texts() == ()
