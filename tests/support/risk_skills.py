"""Shared risk skills test support; no collected test cases."""

from __future__ import annotations

from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.skills.registry import SkillContext
from tests.support.harness import FakeRetrieval, make_deps
from tests.support.harness_data import versions

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
        deps=make_deps(retrieval or FakeRetrieval(), gateway, judge_model_id="gpt-6-sol"),
        evidence_lookup=lambda _u, _ids: (),
        doc_type_lookup=lambda _u, ids: {d: (doc_types or {}).get(d) for d in ids if d in (doc_types or {})},
        trace_id="d" * 32,
        run_id="d" * 32,
    )


ANSWER_CLAUSE = {"claims": [{"text": CLAUSE, "citation_chunk_ids": ["c1"]}]}


ANSWER_LABEL = {
    "claims": [
        {"text": "Glimepiride 每日最高之建議劑量為 8mg。", "citation_chunk_ids": ["c1"]},
        {"text": "禁忌：胰島素依賴型糖尿病、糖尿性昏迷、酮酸中毒。", "citation_chunk_ids": ["c1"]},
    ]
}
