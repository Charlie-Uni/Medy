"""Shared skill matrix test support; no collected test cases."""

from __future__ import annotations

from medops.domain.common import Dept, DocType
from medops.domain.identity import UserContext
from medops.infrastructure.llm.fake import FakeModelGateway
from medops.skills.registry import SkillContext
from tests.support.harness import LABEL as HARNESS_LABEL
from tests.support.harness import FakeRetrieval, make_deps
from tests.support.harness_data import evidence, versions
from tests.support.label_query import ANSWER as LQ_ANSWER
from tests.support.label_query import INPUT as LQ_INPUT
from tests.support.risk_skills import ANSWER_CLAUSE, ANSWER_LABEL, CLAUSE, LABEL, NARRATIVE
from tests.support.skill_judgments import supported_reply

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
        deps=make_deps(
            retrieval if retrieval is not None else FakeRetrieval(*items),
            gateway,
            judge_model_id="gpt-6-sol"
            if spec["purpose"] in ("skill:protocol_deviation", "skill:off_label_check")
            else None,
        ),
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
        if spec["purpose"] in ("skill:protocol_deviation", "skill:off_label_check"):
            script["skill:verify_judgment"] = [supported_reply("deviation" if spec["dept"] == "CO" else "dose")]
    script.update(overrides)
    return FakeModelGateway(script)
