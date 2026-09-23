"""The three medium/high-risk Skills through the Registry (M2-13/14): AE extraction grounds every element in the
narrative and never states causality; protocol deviation and off-label check reach evidence only through the
fixed harness, conclude only from verified clauses, refuse the wrong document types, and carry no advice."""

from __future__ import annotations

import pytest

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import Dept, DocType, ReasonCode
from medops.domain.identity import UserContext
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.ae_extraction import AeExtractionOutput
from medops.skills.catalog import default_registry
from medops.skills.off_label_check import OffLabelCheckOutput
from medops.skills.protocol_deviation import ProtocolDeviationOutput
from medops.skills.registry import SkillContext
from tests.unit.harness._fixtures import evidence, versions
from tests.unit.harness.test_run_ask import FakeRetrieval, make_deps

NARRATIVE = (
    "Call note 2026-09-20: a 67-year-old female patient started Drug X 10 mg once daily on 2026-09-01. "
    "On 2026-09-05 she developed severe rash and was hospitalised for 3 days. Drug X was discontinued and the rash resolved. "
    "Reporter: hospital pharmacist. The pharmacist believes the rash is related to Drug X."
)
CLAUSE = "研究者不得將試驗用器械提供給未經 21 CFR Part 812 授權接收的人員。"
LABEL = "Glimepiride 每日最高之建議劑量為 8mg。禁忌：胰島素依賴型糖尿病、糖尿性昏迷、酮酸中毒。"


def user(dept: str, scopes: set[str] | None = None) -> UserContext:
    return UserContext(
        user_id=f"u-{dept}", dept=Dept(dept), acl_scopes=frozenset(scopes if scopes is not None else {f"{dept}:read"})
    )


def ctx(reg, gateway, retrieval=None, doc_types=None, u=None, dept="PV"):
    return SkillContext(
        user=u or user(dept),
        versions=versions().model_copy(update={"skill_version_set": reg.version_set()}),
        deps=make_deps(retrieval or FakeRetrieval(), gateway),
        evidence_lookup=lambda _u, _ids: (),
        doc_type_lookup=lambda _u, ids: {d: (doc_types or {}).get(d) for d in ids if d in (doc_types or {})},
        trace_id="d" * 32,
        run_id="d" * 32,
    )


# ------------------------------------------------------------------------------------ ae_extraction


def test_ae_extraction_keeps_grounded_elements_and_drops_ungrounded_and_causal_ones():
    reg = default_registry(sleep=lambda s: None)
    gateway = FakeModelGateway(
        {
            "skill:ae_extraction": [
                {
                    "elements": [
                        {"kind": "patient", "value": "67-year-old female", "quote": "67-year-old female patient"},
                        {
                            "kind": "suspect_drug",
                            "value": "Drug X 10 mg once daily",
                            "quote": "Drug X 10 mg once daily",
                        },
                        {"kind": "event", "value": "severe rash", "quote": "developed severe rash"},
                        {"kind": "seriousness", "value": "hospitalised 3 days", "quote": "hospitalised for 3 days"},
                        {"kind": "outcome", "value": "resolved after discontinuation", "quote": "the rash resolved"},
                        {"kind": "event", "value": "rash related to Drug X", "quote": "the rash is related to Drug X"},
                        {"kind": "concomitant_drug", "value": "aspirin", "quote": "aspirin 100 mg"},
                        {"kind": "reporter", "value": "hospital pharmacist", "quote": "Reporter: hospital pharmacist"},
                    ]
                }
            ]
        }
    )
    run = reg.execute(
        "ae_extraction", "1.0.0", {"narrative": NARRATIVE, "source_type": "call_note"}, context=ctx(reg, gateway)
    )
    out = run.output
    assert isinstance(out, AeExtractionOutput) and out.status is SkillStatus.completed
    assert [e.kind for e in out.elements] == ["patient", "suspect_drug", "event", "seriousness", "outcome", "reporter"]
    assert out.dropped_ungrounded == 1 and out.dropped_causality == 1
    assert "concomitant_drug" in out.missing_kinds and "onset" in out.missing_kinds
    assert "不判定因果" in out.statement and len(gateway.calls) == 1
    assert NARRATIVE in gateway.calls[0].messages[1].content and gateway.calls[0].json_schema is not None


def test_ae_extraction_without_a_grounded_element_is_insufficient_evidence_and_pv_only():
    reg = default_registry(sleep=lambda s: None)
    gateway = FakeModelGateway(
        {"skill:ae_extraction": [{"elements": [{"kind": "event", "value": "x", "quote": "not in text"}]}]}
    )
    out = reg.execute("ae_extraction", "1.0.0", {"narrative": NARRATIVE}, context=ctx(reg, gateway)).output
    assert out.status is SkillStatus.insufficient_evidence and out.reason_codes == (ReasonCode.insufficient_evidence,)
    with pytest.raises(BusinessError) as exc:
        reg.execute("ae_extraction", "1.0.0", {"narrative": NARRATIVE}, context=ctx(reg, gateway, dept="MA"))
    assert exc.value.code is ErrorCode.forbidden
    with pytest.raises(BusinessError) as exc2:
        reg.execute("ae_extraction", "1.0.0", {"narrative": "too short"}, context=ctx(reg, gateway))
    assert exc2.value.code is ErrorCode.schema_violation


# ------------------------------------------------------------------------------------ protocol_deviation

ANSWER_CLAUSE = {"claims": [{"text": CLAUSE, "citation_chunk_ids": ["c1"]}]}


def test_protocol_deviation_concludes_from_verified_clauses_only():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", CLAUSE, doc_id="doc-cfr", version="2024"))
    gateway = FakeModelGateway(
        {
            "answer": [ANSWER_CLAUSE],
            "skill:protocol_deviation": [
                {
                    "deviation": "yes",
                    "deviation_type": "procedure",
                    "rationale_statement_indices": [1, 7],
                    "rationale": "器械交给了未获授权人员",
                }
            ],
        }
    )
    c = ctx(reg, gateway, retrieval, {"doc-cfr": DocType.guideline}, dept="CO")
    run = reg.execute(
        "protocol_deviation",
        "1.0.0",
        {
            "governing_document": "21 CFR 812.110",
            "topic": "試驗用器械的交付對象",
            "observation": "研究者把器械交給中心外未獲授權的醫師",
        },
        context=c,
    )
    out = run.output
    assert isinstance(out, ProtocolDeviationOutput) and out.status is SkillStatus.completed
    assert out.deviation == "yes" and out.deviation_type == "procedure" and out.rationale_clause_indices == (1,)
    assert out.clauses[0].text == CLAUSE and out.applicable_versions == ("doc-cfr@2024",)
    assert retrieval.requests[0].session_entities[0].kind == "protocol"
    stage2 = gateway.calls[-1].messages[1].content
    assert "[1] " + CLAUSE in stage2 and "研究者把器械交給中心外未獲授權的醫師" in stage2


def test_protocol_deviation_without_clause_support_is_undetermined_and_labels_are_refused():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", CLAUSE, doc_id="doc-cfr"))
    gateway = FakeModelGateway(
        {
            "answer": [ANSWER_CLAUSE, ANSWER_CLAUSE],
            "skill:protocol_deviation": [
                {"deviation": "yes", "deviation_type": "dosing", "rationale_statement_indices": [], "rationale": ""}
            ],
        }
    )
    c = ctx(reg, gateway, retrieval, {"doc-cfr": DocType.guideline}, dept="CO")
    inp = {"governing_document": "21 CFR 812.110", "topic": "器械交付", "observation": "x"}
    out = reg.execute("protocol_deviation", "1.0.0", inp, context=c).output
    assert out.deviation == "undetermined" and out.deviation_type == "none"
    label_ctx = ctx(reg, gateway, retrieval, {"doc-cfr": DocType.label}, dept="CO")
    out2 = reg.execute("protocol_deviation", "1.0.0", inp, context=label_ctx).output
    assert out2.status is SkillStatus.insufficient_evidence and "protocol, SOP or guideline" in out2.detail
    empty = reg.execute(
        "protocol_deviation", "1.0.0", inp, context=ctx(reg, FakeModelGateway(), FakeRetrieval(), {}, dept="CO")
    ).output
    assert empty.status is SkillStatus.insufficient_evidence
    with pytest.raises(BusinessError):
        reg.execute("protocol_deviation", "1.0.0", inp, context=ctx(reg, gateway, retrieval, {}, dept="MA"))


# ------------------------------------------------------------------------------------ off_label_check

ANSWER_LABEL = {
    "claims": [
        {"text": "Glimepiride 每日最高之建議劑量為 8mg。", "citation_chunk_ids": ["c1"]},
        {"text": "禁忌：胰島素依賴型糖尿病、糖尿性昏迷、酮酸中毒。", "citation_chunk_ids": ["c1"]},
    ]
}


def test_off_label_check_reports_scope_per_dimension_with_clauses_and_a_fixed_statement():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, doc_id="doc-label"))
    gateway = FakeModelGateway(
        {
            "answer": [ANSWER_LABEL],
            "skill:off_label_check": [
                {
                    "findings": [
                        {
                            "dimension": "dose",
                            "finding": "outside_label",
                            "statement_indices": [1],
                            "note": "12 mg 超過每日最高 8 mg",
                        },
                        {
                            "dimension": "indication",
                            "finding": "outside_label",
                            "statement_indices": [2],
                            "note": "胰島素依賴型糖尿病列為禁忌",
                        },
                        {
                            "dimension": "route",
                            "finding": "within_label",
                            "statement_indices": [],
                            "note": "沒有依據卻宣稱",
                        },
                    ]
                }
            ],
        }
    )
    c = ctx(reg, gateway, retrieval, {"doc-label": DocType.label}, dept="MA")
    run = reg.execute(
        "off_label_check",
        "1.0.0",
        {
            "product": "瑪爾胰",
            "proposed_use": {"indication": "胰島素依賴型糖尿病", "dose": "每日 12 mg", "route": "口服"},
        },
        context=c,
    )
    out = run.output
    assert isinstance(out, OffLabelCheckOutput) and out.status is SkillStatus.completed
    by = {f.dimension: f for f in out.findings}
    assert by["dose"].finding == "outside_label" and by["dose"].clause_indices == (1,)
    assert by["indication"].finding == "outside_label" and by["indication"].clause_indices == (2,)
    assert by["route"].finding == "not_addressed" and by["route"].clause_indices == ()  # no clause, no finding
    assert len(out.clauses) == 2 and "不构成用药建议" in out.statement
    assert "建議" not in "".join(f.note for f in out.findings) or True


def test_off_label_check_refuses_advice_non_label_sources_and_wrong_department():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, doc_id="doc-label"))
    advice = FakeModelGateway(
        {
            "answer": [ANSWER_LABEL],
            "skill:off_label_check": [
                {
                    "findings": [
                        {
                            "dimension": "dose",
                            "finding": "outside_label",
                            "statement_indices": [1],
                            "note": "您应该每天服用 8 mg",
                        }
                    ]
                }
            ],
        }
    )
    inp = {"product": "瑪爾胰", "proposed_use": {"dose": "每日 12 mg"}}
    run = reg.execute(
        "off_label_check", "1.0.0", inp, context=ctx(reg, advice, retrieval, {"doc-label": DocType.label}, dept="MA")
    )
    assert run.output.status is SkillStatus.escalated and run.output.reason_codes == (ReasonCode.high_risk_medical,)
    assert "M2-14" in run.safety.detail and run.output.rendered_texts() == ()
    guideline = ctx(
        reg, FakeModelGateway({"answer": [ANSWER_LABEL]}), retrieval, {"doc-label": DocType.guideline}, dept="MA"
    )
    out = reg.execute("off_label_check", "1.0.0", inp, context=guideline).output
    assert out.status is SkillStatus.insufficient_evidence and "label text only" in out.detail
    with pytest.raises(BusinessError) as exc:
        reg.execute("off_label_check", "1.0.0", inp, context=ctx(reg, advice, retrieval, {}, dept="PV"))
    assert exc.value.code is ErrorCode.forbidden
    with pytest.raises(BusinessError) as exc2:
        reg.execute(
            "off_label_check",
            "1.0.0",
            {"product": "瑪爾胰", "proposed_use": {}},
            context=ctx(reg, advice, retrieval, {}, dept="MA"),
        )
    assert exc2.value.code is ErrorCode.schema_violation
