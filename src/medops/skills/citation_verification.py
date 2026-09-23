"""Skill `citation_verification` (医学引用验证, baseline 5.6, low risk): for each submitted claim, the support
status against the chunks it cites and the sources. Cited chunks are re-read from the fact plane under the
caller's identity (invisible or unknown ids are reported, never guessed), screened for injected content
(safety layer 2), and judged by the same verifier as the harness (ADR-0011). No text is generated."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from medops.domain.answer import Claim
from medops.domain.common import DomainModel, NonEmptyStr, RiskLevel
from medops.domain.evidence import Citation
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.domain.verification import Verdict
from medops.safety.checks import screen_evidence
from medops.skills.registry import RegisteredSkill, SkillContext
from medops.verification.verifier import VERIFIER_VERSION, verify_claims

SPEC = SkillSpec(
    name="citation_verification",
    version="1.0.0",
    description="医学引用验证：每条 claim 的支持状态与来源",
    risk=RiskLevel.low,
    required_scopes=("$dept:read",),
    timeout_s=60,
    parallel_safe=True,
    idempotent=True,
)

MAX_CLAIMS = 20


class ClaimToVerify(DomainModel):
    text: Annotated[str, Field(min_length=1, max_length=1000)]
    citation_chunk_ids: tuple[NonEmptyStr, ...] = Field(min_length=1, max_length=8)


class CitationVerificationInput(DomainModel):
    claims: tuple[ClaimToVerify, ...] = Field(min_length=1, max_length=MAX_CLAIMS)


class ClaimVerdict(DomainModel):
    text: NonEmptyStr
    verdict: Verdict
    sources: tuple[Citation, ...] = ()
    unknown_citations: tuple[str, ...] = ()  # not visible to the caller, not a UUID, or screened out
    reason: str = ""


class CitationVerificationOutput(SkillOutput):
    verdicts: tuple[ClaimVerdict, ...] = ()
    verifier_version: str = ""


def _run(ctx: SkillContext, inp: CitationVerificationInput) -> CitationVerificationOutput:
    wanted = sorted({cid for claim in inp.claims for cid in claim.citation_chunk_ids})
    visible, flagged = screen_evidence(tuple(ctx.evidence_lookup(ctx.user, wanted)))
    by_id = {e.citation.chunk_id: e for e in visible}
    verdicts: list[ClaimVerdict] = []
    for item in inp.claims:
        known = [c for c in item.citation_chunk_ids if c in by_id]
        unknown = tuple(c for c in item.citation_chunk_ids if c not in by_id)
        if not known:
            verdicts.append(
                ClaimVerdict(
                    text=item.text,
                    verdict=Verdict.not_supported,
                    unknown_citations=unknown,
                    reason="no cited chunk is visible to the caller",
                )
            )
            continue
        claim = Claim(text=item.text, citation_chunk_ids=tuple(known))
        cited = [by_id[c] for c in known]
        vr = verify_claims(
            [claim],
            cited,
            gateway=ctx.deps.gateway,
            judge_model_id=ctx.deps.judge_model_id,
            timeout_s=ctx.deps.specs["verify"].timeout_s,
        )
        if vr.contradicted:
            verdict = Verdict.contradicted
        elif vr.unsupported or not vr.structural_ok:
            verdict = Verdict.not_supported
        else:
            verdict = Verdict.supported
        supporting = {
            e.evidence_chunk_id for e in vr.elements if e.verdict is Verdict.supported and e.evidence_chunk_id
        }
        sources = tuple(by_id[c].citation for c in known if c in supporting)
        if verdict is Verdict.supported and not sources:
            sources = tuple(e.citation for e in cited)
        verdicts.append(
            ClaimVerdict(
                text=item.text,
                verdict=verdict,
                sources=sources,
                unknown_citations=unknown,
                reason="; ".join(e.reason for e in vr.elements if e.reason)[:300],
            )
        )
    counts = {v.value: sum(1 for x in verdicts if x.verdict is v) for v in Verdict}
    detail = f"verified {len(verdicts)} claim(s): {counts}"
    if flagged:
        detail += f"; {len(flagged)} cited chunk(s) screened out as injected content"
    return CitationVerificationOutput(
        status=SkillStatus.completed, verdicts=tuple(verdicts), verifier_version=VERIFIER_VERSION, detail=detail
    )


ENTRY = RegisteredSkill(
    spec=SPEC, input_model=CitationVerificationInput, output_model=CitationVerificationOutput, handler=_run
)
