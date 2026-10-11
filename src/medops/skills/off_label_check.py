"""Skill `off_label_check` (超说明书用药检查, baseline 5.6, high risk): whether a proposed use falls inside the label's
wording per dimension (indication, population, dose, route), with the clauses relied on and a fixed statement.
No recommendation (M2-14): the output carries none, and the Registry's safety layer 3 refuses advice phrasing."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field, StrictInt, model_validator

from medops.domain.answer import Claim
from medops.domain.common import DocType, DomainModel, ReasonCode, RiskLevel
from medops.domain.evidence import Citation
from medops.domain.intent import Entity
from medops.domain.safety import SafetyDecision
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.domain.skill_judgment import JudgmentVerification
from medops.infrastructure.llm.gateway import ModelOutputInvalid
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
    name="off_label_check",
    version="1.0.0",
    description="超说明书用药检查：是否落在说明书范围、依据条款、固定声明；不提供建议",
    risk=RiskLevel.high,
    required_scopes=("MA:read",),
    timeout_s=120,
    parallel_safe=True,
    idempotent=True,
)
DIMENSIONS: tuple[str, ...] = ("indication", "population", "dose", "route")
FINDINGS: tuple[str, ...] = ("within_label", "outside_label", "not_addressed")
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string", "enum": list(DIMENSIONS)},
                    "finding": {"type": "string", "enum": list(FINDINGS)},
                    "statement_indices": {"type": "array", "items": {"type": "integer"}},
                    "note": {"type": "string"},
                },
                "required": ["dimension", "finding", "statement_indices", "note"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}
SYSTEM = (
    "你是药品说明书范围核验助手。只能依据下方带编号的、已核验的说明书陈述，逐个维度比对拟议用法："
    "within_label（说明书文字覆盖该用法）、outside_label（说明书文字排除或与之不符，如禁忌、超过最大剂量）、"
    "not_addressed（说明书陈述未涉及）。statement_indices 必须列出支撑该判断的陈述编号；"
    "不得使用说明书以外的知识，不得给出任何用药建议或替代方案，note 只写比对依据。只输出 JSON。"
)


class ProposedUse(DomainModel):
    indication: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    population: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    dose: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    route: Annotated[str, Field(min_length=1, max_length=100)] | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> ProposedUse:
        if not any((self.indication, self.population, self.dose, self.route)):
            raise ValueError("proposed_use needs at least one of indication, population, dose, route")
        return self

    def provided(self) -> dict[str, str]:
        return {k: v for k, v in self.model_dump().items() if v}


class OffLabelCheckInput(DomainModel):
    product: Annotated[str, Field(min_length=1, max_length=120)]
    proposed_use: ProposedUse


class DimensionFinding(DomainModel):
    dimension: Literal["indication", "population", "dose", "route"]
    proposed: str
    finding: Literal["within_label", "outside_label", "not_addressed"]
    clause_indices: tuple[int, ...] = ()
    note: str = ""


class OffLabelCheckOutput(SkillOutput):
    findings: tuple[DimensionFinding, ...] = ()
    clauses: tuple[Claim, ...] = ()
    citations: tuple[Citation, ...] = ()
    judgment_verification: JudgmentVerification | None = None
    statement: Literal[
        "本核验只比对说明书文字范围，不构成用药建议；任何超出说明书的使用须由具资格的专业人员依法规评估"
    ] = "本核验只比对说明书文字范围，不构成用药建议；任何超出说明书的使用须由具资格的专业人员依法规评估"


class _FindingReply(DomainModel):
    dimension: Literal["indication", "population", "dose", "route"]
    finding: Literal["within_label", "outside_label", "not_addressed"]
    statement_indices: tuple[StrictInt, ...]
    note: Annotated[str, Field(strict=True, max_length=300)]


class _OffLabelReply(DomainModel):
    findings: tuple[_FindingReply, ...] = Field(min_length=1, max_length=4)


def _run(ctx: SkillContext, inp: OffLabelCheckInput) -> OffLabelCheckOutput:
    use = inp.proposed_use.provided()
    query = f"{inp.product} 適應症 用法用量 禁忌 {' '.join(use.values())}"
    run = grounded_run(ctx, query, (Entity(kind="drug", value=inp.product),))
    answer = run.state.answer
    if answer is None:
        esc = run.state.escalation
        codes = esc.reason_codes if esc is not None else (ReasonCode.insufficient_evidence,)
        status = (
            SkillStatus.insufficient_evidence if ReasonCode.insufficient_evidence in codes else SkillStatus.escalated
        )
        return OffLabelCheckOutput(status=status, reason_codes=codes, detail=esc.detail if esc else "")
    doc_ids = sorted({c.doc_id for c in answer.citations})
    doc_types = ctx.doc_type_lookup(ctx.user, doc_ids)
    if any(doc_types.get(d) is not DocType.label for d in doc_ids):
        return OffLabelCheckOutput(
            status=SkillStatus.insufficient_evidence,
            reason_codes=(ReasonCode.insufficient_evidence,),
            detail="the check compares against label text only; the answer relied on a non-label document",
        )
    clauses = answer.claims
    parsed = structured_call(
        ctx,
        purpose="skill:off_label_check",
        system=SYSTEM,
        user=(
            f"产品：{inp.product}\n拟议用法：\n"
            + "\n".join(f"- {k}: {v}" for k, v in use.items())
            + f"\n\n已核验的说明书陈述：\n{numbered_statements(clauses)}"
        ),
        schema=SCHEMA,
    )
    reply = validate_structured(parsed, _OffLabelReply)
    if len(reply.findings) != len(use) or {f.dimension for f in reply.findings} != set(use):
        raise ModelOutputInvalid("off-label dimensions missing, duplicate or unexpected")
    by_dim: dict[str, _FindingReply] = {f.dimension: f for f in reply.findings}
    findings: list[DimensionFinding] = []
    for dim, proposed in use.items():
        item = by_dim[dim]
        indices = tuple(dict.fromkeys(item.statement_indices))
        findings.append(
            DimensionFinding(
                dimension=dim,  # type: ignore[arg-type]
                proposed=proposed,
                finding=item.finding,
                clause_indices=indices,
                note=item.note,
            )
        )
    candidate = OffLabelCheckOutput(
        status=SkillStatus.completed,
        detail="; ".join(f"{f.dimension}={f.finding}" for f in findings),
        findings=tuple(findings),
        clauses=clauses,
        citations=answer.citations,
        historical_notice=answer.historical_notice,
    )
    safety = check_output_text(candidate.rendered_texts(), off_label=True)
    if safety.decision is not SafetyDecision.allow:
        return candidate.model_copy(update={"status": SkillStatus.escalated, "reason_codes": safety.reason_codes})
    check = verify_final_judgments(
        ctx,
        tuple(
            BusinessJudgment(
                key=f.dimension,
                task="off_label_check",
                observation=f.proposed,
                conclusion=f.finding,
                category=f.dimension,
                rationale=f.note,
                clause_indices=f.clause_indices,
            )
            for f in findings
        ),
        clauses,
    )
    if not check.supported:
        return OffLabelCheckOutput(
            status=SkillStatus.escalated if check.contradicted else SkillStatus.insufficient_evidence,
            reason_codes=(ReasonCode.unsupported_conclusion,),
            detail="final scope findings not supported; comparison requires review",
            findings=tuple(
                DimensionFinding(dimension=f.dimension, proposed=f.proposed, finding="not_addressed") for f in findings
            ),
            clauses=clauses,
            citations=answer.citations,
            historical_notice=answer.historical_notice,
            judgment_verification=check,
        )
    return candidate.model_copy(update={"judgment_verification": check})


ENTRY = RegisteredSkill(spec=SPEC, input_model=OffLabelCheckInput, output_model=OffLabelCheckOutput, handler=_run)
