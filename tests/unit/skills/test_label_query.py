"""`label_query` through the Registry: label text with versioned citations, or an explicit insufficient-evidence
status when the harness abstains or the answer leans on a non-label document."""

from __future__ import annotations

import pytest

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import Dept, DocType, ReasonCode
from medops.domain.identity import UserContext
from medops.domain.skill import SkillStatus
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.catalog import default_registry
from medops.skills.label_query import LabelQueryOutput
from tests.support.harness import LABEL, FakeRetrieval
from tests.support.harness_data import evidence
from tests.support.label_query import ANSWER, INPUT, ctx


def test_label_answer_returns_excerpts_with_versioned_citations():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, doc_id="doc-1"))
    c = ctx(retrieval, FakeModelGateway({"answer": [ANSWER]}), {"doc-1": DocType.label}, reg)
    run = reg.execute("label_query", "1.0.0", INPUT, context=c)
    out = run.output
    assert isinstance(out, LabelQueryOutput) and out.status is SkillStatus.completed
    assert [e.text for e in out.excerpts] == [LABEL] and out.citations[0].chunk_id == "c1"
    assert out.citations[0].version == "v1" and out.claims[0].citation_chunk_ids == ("c1",)
    assert retrieval.requests[0].session_entities[0].value == "拔痛酸錠"
    assert "label_query@1.0.0" in c.versions.skill_version_set and run.attempts[-1].outcome == "ok"


def test_answer_from_a_non_label_document_is_insufficient_evidence():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, doc_id="doc-9"))
    c = ctx(retrieval, FakeModelGateway({"answer": [ANSWER]}), {"doc-9": DocType.guideline}, reg)
    out = reg.execute("label_query", "1.0.0", INPUT, context=c).output
    assert out.status is SkillStatus.insufficient_evidence and out.reason_codes == (ReasonCode.insufficient_evidence,)
    assert "non-label" in out.detail and out.rendered_texts() == ()


def test_harness_abstention_maps_to_insufficient_evidence_with_its_reason_codes():
    reg = default_registry(sleep=lambda s: None)
    c = ctx(FakeRetrieval(), FakeModelGateway(), {}, reg)
    out = reg.execute("label_query", "1.0.0", INPUT, context=c).output
    assert out.status is SkillStatus.insufficient_evidence and ReasonCode.insufficient_evidence in out.reason_codes


def test_caller_without_read_scope_is_denied_before_any_retrieval():
    reg = default_registry(sleep=lambda s: None)
    retrieval = FakeRetrieval(evidence("c1", LABEL, doc_id="doc-1"))
    denied = UserContext(user_id="u9", dept=Dept.CO, acl_scopes=frozenset({"CO:write"}))
    c = ctx(retrieval, FakeModelGateway({"answer": [ANSWER]}), {"doc-1": DocType.label}, reg, denied)
    with pytest.raises(BusinessError) as exc:
        reg.execute("label_query", "1.0.0", INPUT, context=c)
    assert exc.value.code is ErrorCode.forbidden and retrieval.requests == []


@pytest.mark.parametrize(
    "raw", [{"product": "", "question": "x"}, {"product": "p"}, {"product": "p", "question": "q" * 501}]
)
def test_input_schema_is_enforced(raw):
    reg = default_registry(sleep=lambda s: None)
    c = ctx(FakeRetrieval(), FakeModelGateway(), {}, reg)
    with pytest.raises(BusinessError) as exc:
        reg.execute("label_query", "1.0.0", raw, context=c)
    assert exc.value.code is ErrorCode.schema_violation
