"""Skill `protocol_deviation` (方案偏离核验, baseline 5.6, medium risk): whether an observed fact deviates from the
governing document (protocol / SOP / guideline clause), the deviation type, the applicable document version and
the clause citations. Stage 1 is the fixed harness run (verified clause statements); stage 2 is one structured
comparison over those statements only, and every conclusion must point at them."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from medops.domain.answer import Claim
from medops.domain.common import DocType, DomainModel, ReasonCode, RiskLevel
from medops.domain.evidence import Citation
from medops.domain.intent import Entity
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.skills._structured import grounded_run, numbered_statements, structured_call, valid_indices
from medops.skills.registry import RegisteredSkill, SkillContext

SPEC = SkillSpec(
    name="protocol_deviation",
    version="1.0.0",
    description="方案偏离核验：是否偏离、类型、适用版本和条款引用",
    risk=RiskLevel.medium,
    required_scopes=("CO:read",),
    timeout_s=120,
    parallel_safe=True,
    idempotent=True,
)
GOVERNING_TYPES = (DocType.protocol, DocType.sop, DocType.guideline)
DEVIATION_TYPES: tuple[str, ...] = (
    "visit_window",
    "dosing",
    "eligibility",
    "procedure",
    "consent",
    "documentation",
    "safety_reporting",
    "other",
    "none",
)
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "deviation": {"type": "string", "enum": ["yes", "no", "undetermined"]},
        "deviation_type": {"type": "string", "enum": list(DEVIATION_TYPES)},
        "rationale_statement_indices": {"type": "array", "items": {"type": "integer"}},
        "rationale": {"type": "string"},
    },
    "required": ["deviation", "deviation_type", "rationale_statement_indices", "rationale"],
    "additionalProperties": False,
}
SYSTEM = (
    "你是临床运营的方案偏离核验助手。只能依据下方带编号的、已核验的文件条款陈述来比对所述事实。"
    "判断所述事实是否偏离条款：yes / no；条款没有覆盖该事实时输出 undetermined。"
    "rationale_statement_indices 必须列出支撑结论的条款编号；不得使用条款以外的知识，不得给出处置建议。"
    "只输出 JSON。"
)


class ProtocolDeviationInput(DomainModel):
    governing_document: Annotated[str, Field(min_length=1, max_length=120)]  # protocol id, regulation, document key
    topic: Annotated[str, Field(min_length=1, max_length=200)]  # the clause topic to look up
    observation: Annotated[str, Field(min_length=1, max_length=1000)]  # what happened


class ProtocolDeviationOutput(SkillOutput):
    deviation: Literal["yes", "no", "undetermined"] = "undetermined"
    deviation_type: str = "none"
    clauses: tuple[Claim, ...] = ()
    citations: tuple[Citation, ...] = ()
    applicable_versions: tuple[str, ...] = ()
    rationale: str = ""
    rationale_clause_indices: tuple[int, ...] = ()
    statement: Literal["结论仅比对文件条款与所述事实，不构成合规判定或处置建议"] = (
        "结论仅比对文件条款与所述事实，不构成合规判定或处置建议"
    )


def _run(ctx: SkillContext, inp: ProtocolDeviationInput) -> ProtocolDeviationOutput:
    run = grounded_run(
        ctx,
        f"{inp.governing_document} {inp.topic}",
        (Entity(kind="protocol", value=inp.governing_document),),
    )
    answer = run.state.answer
    if answer is None:
        esc = run.state.escalation
        codes = esc.reason_codes if esc is not None else (ReasonCode.insufficient_evidence,)
        status = (
            SkillStatus.insufficient_evidence if ReasonCode.insufficient_evidence in codes else SkillStatus.escalated
        )
        return ProtocolDeviationOutput(status=status, reason_codes=codes, detail=esc.detail if esc else "")
    doc_types = ctx.doc_type_lookup(ctx.user, sorted({c.doc_id for c in answer.citations}))
    wrong = [d for d, t in doc_types.items() if t not in GOVERNING_TYPES]
    if wrong or len(doc_types) < len({c.doc_id for c in answer.citations}):
        return ProtocolDeviationOutput(
            status=SkillStatus.insufficient_evidence,
            reason_codes=(ReasonCode.insufficient_evidence,),
            detail="clauses must come from a protocol, SOP or guideline document",
        )
    clauses = answer.claims
    parsed = structured_call(
        ctx,
        purpose="skill:protocol_deviation",
        system=SYSTEM,
        user=(
            f"文件：{inp.governing_document}\n主题：{inp.topic}\n所述事实：{inp.observation}\n\n"
            f"已核验的条款陈述：\n{numbered_statements(clauses)}"
        ),
        schema=SCHEMA,
    )
    indices = valid_indices(parsed.get("rationale_statement_indices"), len(clauses))
    deviation = parsed.get("deviation") if parsed.get("deviation") in ("yes", "no", "undetermined") else "undetermined"
    dev_type = str(parsed.get("deviation_type")) if parsed.get("deviation_type") in DEVIATION_TYPES else "other"
    if deviation != "undetermined" and not indices:
        deviation, dev_type = "undetermined", "none"  # a conclusion that cites no clause is not a conclusion
    if deviation == "no":
        dev_type = "none"
    versions = tuple(sorted({f"{c.doc_id}@{c.version}" for c in answer.citations}))
    return ProtocolDeviationOutput(
        status=SkillStatus.completed,
        detail=f"deviation={deviation} type={dev_type} clauses={len(clauses)}",
        deviation=deviation,  # type: ignore[arg-type]
        deviation_type=dev_type,
        clauses=clauses,
        citations=answer.citations,
        applicable_versions=versions,
        rationale=str(parsed.get("rationale", ""))[:600],
        rationale_clause_indices=indices,
    )


ENTRY = RegisteredSkill(
    spec=SPEC, input_model=ProtocolDeviationInput, output_model=ProtocolDeviationOutput, handler=_run
)
