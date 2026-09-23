"""Skill `label_query` (说明书查询, baseline 5.6, low risk): original label text, versioned citations, or an explicit
insufficient-evidence status. It runs the fixed harness (Intent -> Retrieve -> Verify -> Safety -> Answer) with
the product as a session entity, then checks that every cited document is a label; an answer that leans on a
non-label document is reported as insufficient evidence rather than passed off as label text."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from medops.domain.answer import Claim
from medops.domain.common import DocType, DomainModel, NonEmptyStr, ReasonCode, RiskLevel
from medops.domain.evidence import Citation
from medops.domain.intent import Entity
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.harness.runtime import initial_state, run_ask
from medops.skills.registry import RegisteredSkill, SkillContext

SPEC = SkillSpec(
    name="label_query",
    version="1.0.0",
    description="药品说明书查询：原文片段、版本化引用、证据不足状态",
    risk=RiskLevel.low,
    required_scopes=("$dept:read",),
    timeout_s=90,
    parallel_safe=True,
    idempotent=True,
)


class LabelQueryInput(DomainModel):
    product: Annotated[str, Field(min_length=1, max_length=120)]
    question: Annotated[str, Field(min_length=1, max_length=500)]


class LabelExcerpt(DomainModel):
    text: NonEmptyStr
    citation: Citation


class LabelQueryOutput(SkillOutput):
    claims: tuple[Claim, ...] = ()
    excerpts: tuple[LabelExcerpt, ...] = ()
    citations: tuple[Citation, ...] = ()
    historical_notice: bool = False


def _run(ctx: SkillContext, inp: LabelQueryInput) -> LabelQueryOutput:
    state = initial_state(
        user=ctx.user,
        query=f"{inp.product} {inp.question}",
        versions=ctx.versions,
        trace_id=ctx.trace_id,
        run_id=ctx.run_id,
        session_entities=(Entity(kind="drug", value=inp.product),),
    )
    run = run_ask(state, ctx.deps)
    answer = run.state.answer
    if answer is None:
        esc = run.state.escalation
        codes = esc.reason_codes if esc is not None else (ReasonCode.insufficient_evidence,)
        status = (
            SkillStatus.insufficient_evidence if ReasonCode.insufficient_evidence in codes else SkillStatus.escalated
        )
        return LabelQueryOutput(status=status, reason_codes=codes, detail=esc.detail if esc is not None else "")
    doc_ids = sorted({c.doc_id for c in answer.citations})
    doc_types = ctx.doc_type_lookup(ctx.user, doc_ids)
    non_label = [d for d in doc_ids if doc_types.get(d) is not DocType.label]
    if non_label:
        return LabelQueryOutput(
            status=SkillStatus.insufficient_evidence,
            reason_codes=(ReasonCode.insufficient_evidence,),
            detail=f"answer cites {len(non_label)} non-label document(s); label_query reports label text only",
        )
    by_id = {e.citation.chunk_id: e for e in run.state.evidence}
    excerpts = tuple(
        LabelExcerpt(text=by_id[c.chunk_id].text, citation=c) for c in answer.citations if c.chunk_id in by_id
    )
    return LabelQueryOutput(
        status=SkillStatus.completed,
        claims=answer.claims,
        excerpts=excerpts,
        citations=answer.citations,
        historical_notice=answer.historical_notice,
    )


ENTRY = RegisteredSkill(spec=SPEC, input_model=LabelQueryInput, output_model=LabelQueryOutput, handler=_run)
