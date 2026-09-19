import hashlib
from datetime import date

import pytest

from medops.domain import (
    AgentState,
    Answer,
    CandidateRef,
    Citation,
    Claim,
    Dept,
    DocStatus,
    ElementKind,
    ElementSupport,
    Evidence,
    Intent,
    IntentType,
    RiskLevel,
    SafetyDecision,
    SafetyResult,
    TokenBudget,
    UserContext,
    Verdict,
    VerifyResult,
    VersionSet,
)

sha = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()  # noqa: E731


def make_evidence(chunk_id="c1", status=DocStatus.active, historical=False, text="每次 0.5 g,每日 2 次"):
    return Evidence(
        citation=Citation(
            doc_id="d1",
            version="2026-01",
            effective_date=date(2026, 1, 1),
            page=3,
            section="用法用量",
            chunk_id=chunk_id,
        ),
        text=text,
        evidence_text_hash=sha(text),
        chunk_content_hash=sha("chunk"),
        status=status,
        historical=historical,
    )


@pytest.fixture
def user():
    return UserContext(
        user_id="u-surrogate-1", dept=Dept.MA, roles=("medical_affairs",), acl_scopes=frozenset({"MA:read"})
    )


@pytest.fixture
def base_state(user):
    return AgentState(
        trace_id="trace-1",
        run_id="trace-1",
        user=user,
        query="示例药品X片成人一次吃多少",
        versions=VersionSet(
            policy_version="pol-1",
            retrieval_version="ret-1",
            skill_version_set=("label_query@1",),
            model_config_version="m-1",
        ),
        budget=TokenBudget(limit=8000, used=0),
    )


@pytest.fixture
def answered_state(base_state):
    ev = make_evidence()
    verify = VerifyResult(
        structural_ok=True,
        elements=(
            ElementSupport(
                kind=ElementKind.dose, text="0.5 g", verdict=Verdict.supported, evidence_chunk_id="c1", confidence=0.9
            ),
        ),
        verifier_version="v-1",
    )
    safety = SafetyResult(decision=SafetyDecision.allow, checker_version="s-1")
    answer = Answer(
        claims=(Claim(text="成人每次 0.5 g，每日 2 次", citation_chunk_ids=("c1",)),), citations=(ev.citation,)
    )
    return (
        base_state.advance(
            intent=Intent(
                type=IntentType.label_query, target_skill="label_query", risk=RiskLevel.low, confidence=0.9
            ).model_dump()
        )
        .advance(
            rewritten_queries=("示例药品X片 用法用量",),
            candidates=(CandidateRef(chunk_id="c1", source_ranks=({"source": "lexical", "rank": 1},)).model_dump(),),
        )
        .advance(
            evidence=(ev.model_dump(),),
            verify_result=verify.model_dump(),
            safety_result=safety.model_dump(),
            budget={"limit": 8000, "used": 1200},
        )
        .advance(answer=answer.model_dump())
    )
