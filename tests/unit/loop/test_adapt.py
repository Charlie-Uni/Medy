"""Adapt (M4-03): proposals from attributed cases, candidate validation and the INV-EVAL-01 isolation check."""

from __future__ import annotations

import uuid

import pytest

from medops.application.policy_loader import PolicyDiffError
from medops.loop.adapt import (
    Candidate,
    IsolationError,
    check_isolation,
    propose,
    retrieval_auto_diff,
    validate_candidate,
)
from medops.retrieval.hybrid import HybridConfig

CASE = str(uuid.uuid4())
QUERIES = frozenset({"瑪爾胰(glimepiride)每日最高建議劑量是多少?"})


def cases(*specs):
    return [{"case_id": str(uuid.uuid4()), "dept": d, "attribution": a, "human_override": o} for a, d, o in specs]


def test_propose_groups_by_effective_attribution_and_department_with_min_support():
    rows = cases(
        ("retrieval", "MA", None),
        ("retrieval", "MA", None),
        ("retrieval", "MA", None),
        ("generation", "PV", None),
        ("generation", "PV", {"attribution": "knowledge_gap", "by": "r", "note": "", "at": "x"}),
        ("knowledge_gap", "PV", None),
        ("knowledge_gap", "PV", None),
        ("intent", "CO", None),
    )
    at_cap = HybridConfig(k_lexical=20, k_vector=20)
    out = {(p.attribution, p.dept): p for p in propose(rows, current=at_cap, min_support=3)}
    assert set(out) == {
        ("retrieval", "MA"),
        ("knowledge_gap", "PV"),
    }  # the override moves one PV case into the gap group
    p = out[("retrieval", "MA")]
    assert p.suggested_kind == "retrieval_params" and p.auto_diff is None and p.needs_author and "cap" in p.note
    out2 = {
        (p.attribution, p.dept): p
        for p in propose(rows, current=HybridConfig(k_lexical=10, k_vector=20), min_support=2)
    }
    assert (
        out2[("retrieval", "MA")].auto_diff == {"k_lexical": {"from": 10, "to": 20}}
        and not out2[("retrieval", "MA")].needs_author
    )
    kg = out2[("knowledge_gap", "PV")]
    assert (
        kg.suggested_kind is None and len(kg.case_ids) == 3 and not kg.needs_author
    )  # the override moved one case here
    assert ("generation", "PV") not in out2  # only one generation case left after the override
    assert retrieval_auto_diff(at_cap) is None


def good_candidate(**kw) -> Candidate:
    base = {
        "kind": "retrieval_params",
        "name": "hybrid",
        "diff": {"rrf_k": {"from": 60.0, "to": 40.0}},
        "evidence": {"case_ids": [CASE], "summary": "three MA retrieval cases"},
        "created_by": "loop:adapt-v1",
    }
    base.update(kw)
    return Candidate(**base)


def test_valid_candidates_pass_and_get_a_content_addressed_version():
    cur = HybridConfig()
    validate_candidate(good_candidate(), current=cur, forbidden_queries=QUERIES)
    validate_candidate(
        good_candidate(kind="prompt", name="answer_system", diff={"text": "只依据证据作答。"}),
        current=cur,
        forbidden_queries=QUERIES,
    )
    validate_candidate(
        good_candidate(kind="rule", name="intent_rules", diff={"add": [r"\bmy dose\b"]}),
        current=cur,
        forbidden_queries=QUERIES,
    )
    validate_candidate(
        good_candidate(kind="skill", name="label_query", diff={"params": {"max_excerpts": 3}}),
        current=cur,
        forbidden_queries=QUERIES,
    )
    v = good_candidate().with_version()
    assert v.version.startswith("hybrid@") and len(v.version.rsplit("-", 1)[1]) == 8


@pytest.mark.parametrize(
    ("kw", "error"),
    [
        ({"kind": "code"}, PolicyDiffError),
        ({"name": "Bad Name"}, PolicyDiffError),
        ({"diff": {}}, PolicyDiffError),
        ({"diff": {"k_lexical": {"from": 20, "to": 30}}}, PolicyDiffError),  # above the baseline cap
        ({"diff": {"rrf_k": {"from": 50.0, "to": 40.0}}}, PolicyDiffError),  # `from` is not the current value
        ({"diff": {"rrf_k": {"from": 60.0, "to": 60.0}}}, PolicyDiffError),  # changes nothing
        ({"evidence": {}}, PolicyDiffError),
        ({"evidence": {"case_ids": ["ms-0012"]}}, PolicyDiffError),
        ({"evidence": {"case_ids": [CASE], "source": "replay item rp-0007"}}, IsolationError),
        (
            {"kind": "prompt", "name": "answer_system", "diff": {"text": "瑪爾胰(glimepiride)每日最高建議劑量是多少?"}},
            IsolationError,
        ),
        ({"kind": "rule", "name": "intent_rules", "diff": {"add": ["("]}}, PolicyDiffError),
    ],
)
def test_invalid_or_leaking_candidates_are_refused(kw, error):
    with pytest.raises(error):
        validate_candidate(good_candidate(**kw), current=HybridConfig(), forbidden_queries=QUERIES)


def test_isolation_check_normalises_whitespace_and_scans_nested_values():
    c = good_candidate(
        evidence={"case_ids": [CASE], "notes": [{"seen": "  瑪爾胰(glimepiride)每日最高建議劑量是多少?  "}]}
    )
    with pytest.raises(IsolationError):
        check_isolation(c, forbidden_queries=QUERIES)
    check_isolation(good_candidate(), forbidden_queries=QUERIES)
