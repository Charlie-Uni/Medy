"""M5-02 test matrix (record 88): the five delivered Skills × the cross-cutting dimensions, through the Registry with
fakes — permission is checked before any model call, a schema violation never reaches the handler, an empty evidence
set ends in `insufficient_evidence` without a model call, a provider fault ends in a bounded `system_failure`, and no
output ever carries individual medical advice. Functional happy paths are the per-skill tests
(test_label_query, test_citation_verification, test_risk_skills) and the real smoke runs
(`evals/harness/runs/2026-09-23-skill-smoke-v1` / `-v2`)."""

from __future__ import annotations

import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept, DocType, ReasonCode
from medops.domain.identity import UserContext
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.infrastructure.llm.gateway import ModelTimeout
from medops.skills.catalog import default_registry
from medops.skills.registry import SkillContext
from tests.unit.harness._fixtures import evidence, versions
from tests.unit.harness.test_run_ask import LABEL as HARNESS_LABEL
from tests.unit.harness.test_run_ask import FakeRetrieval, make_deps
from tests.unit.skills.test_label_query import ANSWER as LQ_ANSWER
from tests.unit.skills.test_label_query import INPUT as LQ_INPUT
from tests.unit.skills.test_risk_skills import ANSWER_CLAUSE, ANSWER_LABEL, CLAUSE, LABEL, NARRATIVE

ADVICE = "您应该每天服用 100 mg"

SKILLS: dict[str, dict] = {
    "label_query": {
        "dept": "MA",
        "input": LQ_INPUT,
        "evidence": (HARNESS_LABEL, DocType.label),
        "answer": LQ_ANSWER,
        "purpose": None,
        "reply": None,
        "advice_reply": None,
    },
    "citation_verification": {
        "dept": "PV",
        "input": {"claims": [{"text": CLAUSE, "citation_chunk_ids": ["c1"]}]},
        "evidence": (CLAUSE, DocType.guideline),
        "answer": None,
        "purpose": None,
        "reply": None,
        "advice_reply": None,
    },
    "ae_extraction": {
        "dept": "PV",
        "input": {"narrative": NARRATIVE},
        "evidence": None,
        "answer": None,
        "purpose": "skill:ae_extraction",
        "reply": {
            "elements": [{"kind": "patient", "value": "67-year-old female", "quote": "67-year-old female patient"}]
        },
        "advice_reply": {"elements": [{"kind": "patient", "value": ADVICE, "quote": "67-year-old female patient"}]},
    },
    "off_label_check": {
        "dept": "MA",
        "input": {"product": "瑪爾胰", "proposed_use": {"dose": "每日 12 mg"}},
        "evidence": (LABEL, DocType.label),
        "answer": ANSWER_LABEL,
        "purpose": "skill:off_label_check",
        "reply": {
            "findings": [
                {"dimension": "dose", "finding": "outside_label", "statement_indices": [1], "note": "12 mg 超過 8 mg"}
            ]
        },
        "advice_reply": {
            "findings": [{"dimension": "dose", "finding": "outside_label", "statement_indices": [1], "note": ADVICE}]
        },
    },
    "protocol_deviation": {
        "dept": "CO",
        "input": {
            "governing_document": "21 CFR 812.110",
            "topic": "試驗用器械可以提供給哪些人員使用",
            "observation": "研究者將試驗用器械交給未獲授權的醫師使用",
        },
        "evidence": (CLAUSE, DocType.guideline),
        "answer": ANSWER_CLAUSE,
        "purpose": "skill:protocol_deviation",
        "reply": {
            "deviation": "yes",
            "deviation_type": "procedure",
            "rationale_statement_indices": [1],
            "rationale": "器械交给了未获授权人员",
        },
        "advice_reply": {
            "deviation": "yes",
            "deviation_type": "procedure",
            "rationale_statement_indices": [1],
            "rationale": ADVICE,
        },
    },
}
NAMES = tuple(SKILLS)


def user(dept: str, scopes: set[str] | None = None) -> UserContext:
    return UserContext(
        user_id=f"u-{dept}", dept=Dept(dept), acl_scopes=frozenset(scopes if scopes is not None else {f"{dept}:read"})
    )


def context(reg, spec: dict, *, gateway: FakeModelGateway, u: UserContext | None = None, retrieval=None, lookup=None):
    ev = spec["evidence"]
    items = (evidence("c1", ev[0], doc_id="doc-1"),) if ev else ()
    doc_types = {"doc-1": ev[1]} if ev else {}
    return SkillContext(
        user=u or user(spec["dept"]),
        versions=versions().model_copy(update={"skill_version_set": reg.version_set()}),
        deps=make_deps(retrieval if retrieval is not None else FakeRetrieval(*items), gateway),
        evidence_lookup=lookup or (lambda _u, ids: tuple(e for e in items if e.citation.chunk_id in ids)),
        doc_type_lookup=lambda _u, ids: {d: doc_types[d] for d in ids if d in doc_types},
        trace_id="e" * 32,
        run_id="e" * 32,
    )


def scripted(spec: dict, **overrides) -> FakeModelGateway:
    script: dict = {}
    if spec["answer"] is not None:
        script["answer"] = [spec["answer"]] * 6  # every retry re-runs the harness; keep the fault on the skill call
    if spec["purpose"]:
        script[spec["purpose"]] = [spec["reply"]]
    script.update(overrides)
    return FakeModelGateway(script)


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
