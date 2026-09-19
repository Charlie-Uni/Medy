import hashlib
import re
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from medops.domain import (
    DISCLAIMER,
    Answer,
    Chunk,
    Claim,
    Dept,
    DocStatus,
    DocType,
    Document,
    ElementKind,
    ElementSupport,
    Escalation,
    Intent,
    IntentType,
    ReasonCode,
    RiskLevel,
    SafetyDecision,
    SafetyResult,
    TokenBudget,
    UserContext,
    Verdict,
    VerifyResult,
)
from tests.unit.domain.conftest import make_evidence, sha

DOMAIN_SRC = Path(__file__).resolve().parents[3] / "src" / "medops" / "domain"


def test_domain_package_has_no_untyped_dict_contracts():  # INV-HAR-01
    pattern = re.compile(r"dict\[str,\s*Any\]|:\s*Any\b|import Any\b|,\s*Any\b")
    offenders = [p.name for p in DOMAIN_SRC.glob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_models_are_frozen_and_forbid_extra_fields(user):
    with pytest.raises(ValidationError):
        UserContext(user_id="u", dept=Dept.MA, unexpected="x")
    with pytest.raises(ValidationError):
        user.dept = Dept.PV  # type: ignore[misc]


def test_user_scopes_default_deny(user):
    assert (
        user.has_scopes(("MA:read",))
        and not user.has_scopes(("PV:read",))
        and not user.has_scopes(("MA:read", "CO:read"))
    )
    with pytest.raises(ValidationError):
        UserContext(user_id="u", dept=Dept.MA, acl_scopes=frozenset({"read-everything"}))


def test_document_effective_window_rules():
    base = dict(
        doc_id="d1",
        family_id="f1",
        title="t",
        doc_type=DocType.label,
        version="v1",
        source_hash=sha("x"),
        owner_dept=Dept.MA,
    )
    Document(status=DocStatus.draft, **base)
    with pytest.raises(ValidationError, match="effective_from"):
        Document(status=DocStatus.active, **base)
    with pytest.raises(ValidationError, match="after"):
        Document(status=DocStatus.active, effective_from=date(2026, 2, 1), effective_to=date(2026, 1, 1), **base)
    with pytest.raises(ValidationError, match="supersede"):
        Document(status=DocStatus.draft, supersedes="d1", **base)


def test_chunk_hash_and_range_integrity():
    content = "孕妇禁用。"
    ok = Chunk(
        chunk_id="c",
        doc_id="d",
        page=1,
        section="禁忌",
        seq=0,
        char_start=10,
        char_end=15,
        content=content,
        content_hash=sha(content),
    )
    assert ok.content_hash == hashlib.sha256(content.encode()).hexdigest()
    with pytest.raises(ValidationError, match="content_hash"):
        Chunk(
            chunk_id="c",
            doc_id="d",
            page=1,
            section="禁忌",
            seq=0,
            char_start=10,
            char_end=15,
            content=content,
            content_hash=sha("tampered"),
        )
    with pytest.raises(ValidationError, match="char range"):
        Chunk(
            chunk_id="c",
            doc_id="d",
            page=1,
            section="禁忌",
            seq=0,
            char_start=10,
            char_end=12,
            content=content,
            content_hash=sha(content),
        )


def test_evidence_status_rules():
    make_evidence(status=DocStatus.archived, historical=True)
    with pytest.raises(ValidationError, match="draft"):
        make_evidence(status=DocStatus.draft)
    with pytest.raises(ValidationError, match="withdrawn"):
        make_evidence(status=DocStatus.withdrawn)
    with pytest.raises(ValidationError, match="historical"):
        make_evidence(status=DocStatus.archived, historical=False)
    with pytest.raises(ValidationError, match="evidence_text_hash"):
        ev = make_evidence().model_dump()
        ev["text"] = "changed"
        make_evidence.__globals__["Evidence"].model_validate(ev)


def test_intent_risk_floor_and_high_risk_routing():
    with pytest.raises(ValidationError, match="risk >= high"):
        Intent(type=IntentType.off_label_check, risk=RiskLevel.low, confidence=0.5)
    with pytest.raises(ValidationError, match="never routed"):
        Intent(type=IntentType.high_risk, target_skill="label_query", risk=RiskLevel.high, confidence=0.5)
    Intent(type=IntentType.ae_extraction, risk=RiskLevel.high, confidence=1.0)


def test_verify_and_safety_consistency():
    with pytest.raises(ValidationError, match="supported element"):
        ElementSupport(kind=ElementKind.dose, text="0.5 g", verdict=Verdict.supported, confidence=0.9)
    with pytest.raises(ValidationError, match="structural_ok"):
        VerifyResult(structural_ok=True, hallucinated_citations=("ghost",), verifier_version="v")
    vr = VerifyResult(
        structural_ok=True,
        elements=(ElementSupport(kind=ElementKind.dose, text="1", verdict=Verdict.contradicted, confidence=0.8),),
        verifier_version="v",
    )
    assert vr.contradicted and vr.unsupported == ()
    with pytest.raises(ValidationError, match="reason code"):
        SafetyResult(decision=SafetyDecision.refuse, checker_version="s")
    with pytest.raises(ValidationError, match="no reason codes"):
        SafetyResult(decision=SafetyDecision.allow, reason_codes=(ReasonCode.acl_denied,), checker_version="s")


def test_answer_disclaimer_is_fixed_and_claims_must_cite_listed_citations():
    cit = make_evidence().citation
    ans = Answer(claims=(Claim(text="x", citation_chunk_ids=("c1",)),), citations=(cit,))
    assert ans.disclaimer == DISCLAIMER
    with pytest.raises(ValidationError):
        Answer(claims=(Claim(text="x", citation_chunk_ids=("c1",)),), citations=(cit,), disclaimer="仅供参考")
    with pytest.raises(ValidationError, match="not listed"):
        Answer(claims=(Claim(text="x", citation_chunk_ids=("c9",)),), citations=(cit,))
    with pytest.raises(ValidationError):
        Claim(text="x", citation_chunk_ids=())


def test_escalation_requires_reason_codes():
    with pytest.raises(ValidationError):
        Escalation(reason_codes=(), query="q", policy_version="pol-1")
    Escalation(reason_codes=(ReasonCode.insufficient_evidence,), query="q", policy_version="pol-1")


def test_token_budget_cannot_be_exceeded():
    assert TokenBudget(limit=10, used=4).remaining == 6
    with pytest.raises(ValidationError, match="exceeded"):
        TokenBudget(limit=10, used=11)


def test_scope_set_serializes_in_stable_order_for_hashing():
    from medops.core.canonical import canonical_hash

    a = UserContext(user_id="u", dept=Dept.MA, acl_scopes=frozenset(["PV:read", "MA:read", "CO:read"]))
    b = UserContext(user_id="u", dept=Dept.MA, acl_scopes=frozenset(["CO:read", "PV:read", "MA:read"]))
    assert a.model_dump()["acl_scopes"] == ["CO:read", "MA:read", "PV:read"]
    assert a.model_dump_json() == b.model_dump_json() and canonical_hash(a.model_dump()) == canonical_hash(
        b.model_dump()
    )
    assert UserContext.model_validate_json(a.model_dump_json()) == a


def test_skill_version_set_is_order_independent():
    from medops.domain import VersionSet

    x = VersionSet(
        policy_version="p", retrieval_version="r", skill_version_set=("b@1", "a@1", "b@1"), model_config_version="m"
    )
    y = VersionSet(
        policy_version="p", retrieval_version="r", skill_version_set=("a@1", "b@1"), model_config_version="m"
    )
    assert x == y and x.skill_version_set == ("a@1", "b@1")
