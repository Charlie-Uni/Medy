"""Skill `protocol_deviation` (方案偏离核验, baseline 5.6, medium risk): whether an observed fact deviates from the
governing document (protocol / SOP / guideline clause), the deviation type, the applicable document version and
the clause citations. Stage 1 is the fixed harness run (verified clause statements); stage 2 is one structured
comparison over those statements only, and every conclusion must point at them."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, StrictInt

from medops.domain.answer import Claim
from medops.domain.common import DocType, DomainModel, ReasonCode, RiskLevel
from medops.domain.evidence import Citation
from medops.domain.intent import Entity
from medops.domain.safety import SafetyDecision
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.domain.skill_judgment import JudgmentVerification
from medops.safety.checks import check_output_text
from medops.skills._structured import (
    grounded_run,
    numbered_statements,
    structured_call,
    validate_structured,
    verify_final_judgments,
)
from medops.skills.registry import RegisteredSkill, SkillContext
from medops.verification.skill_judgment import BusinessJudgment

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
    judgment_verification: JudgmentVerification | None = None
    statement: Literal["结论仅比对文件条款与所述事实，不构成合规判定或处置建议"] = (
        "结论仅比对文件条款与所述事实，不构成合规判定或处置建议"
    )


class _ProtocolReply(DomainModel):
    deviation: Literal["yes", "no", "undetermined"]
    deviation_type: Literal[
        "visit_window",
        "dosing",
        "eligibility",
        "procedure",
        "consent",
        "documentation",
        "safety_reporting",
        "other",
        "none",
    ]
    rationale_statement_indices: tuple[StrictInt, ...]
    rationale: Annotated[str, Field(strict=True, max_length=600)]


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
    reply = validate_structured(parsed, _ProtocolReply)
    indices = tuple(dict.fromkeys(reply.rationale_statement_indices))
    deviation, dev_type = reply.deviation, reply.deviation_type
    versions = tuple(sorted({f"{c.doc_id}@{c.version}" for c in answer.citations}))
    candidate = ProtocolDeviationOutput(
        status=SkillStatus.completed,
        detail=f"deviation={deviation} type={dev_type} clauses={len(clauses)}",
        deviation=deviation,
        deviation_type=dev_type,
        clauses=clauses,
        citations=answer.citations,
        historical_notice=answer.historical_notice,
        applicable_versions=versions,
        rationale=reply.rationale,
        rationale_clause_indices=indices,
    )
    safety = check_output_text(candidate.rendered_texts())
    if safety.decision is not SafetyDecision.allow:
        # The Registry applies the existing safety gate and discards this payload before returning it.
        return candidate.model_copy(update={"status": SkillStatus.escalated, "reason_codes": safety.reason_codes})
    check = verify_final_judgments(
        ctx,
        (
            BusinessJudgment(
                key="deviation",
                task="protocol_deviation",
                observation=inp.observation,
                conclusion=deviation,
                category=dev_type,
                rationale=reply.rationale,
                clause_indices=indices,
            ),
        ),
        clauses,
    )
    if not check.supported:
        return ProtocolDeviationOutput(
            status=SkillStatus.escalated if check.contradicted else SkillStatus.insufficient_evidence,
            reason_codes=(ReasonCode.unsupported_conclusion,),
            detail="final judgment not supported; comparison requires review",
            clauses=clauses,
            citations=answer.citations,
            applicable_versions=versions,
            historical_notice=answer.historical_notice,
            judgment_verification=check,
        )
    return candidate.model_copy(update={"judgment_verification": check})


ENTRY = RegisteredSkill(
    spec=SPEC, input_model=ProtocolDeviationInput, output_model=ProtocolDeviationOutput, handler=_run
)
