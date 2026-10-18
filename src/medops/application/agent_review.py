"""Compile a bound, item-level internal review from the actual final check.

No evaluator expectations, hidden gold, state writes, public completed status or
model calls. The real driver supplies its own proof and commits this material
under the SAME fact fence. A serialised copy is not publication authority.
"""

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import Field, model_validator

from medops.application.agent_contracts import context_binding
from medops.application.agent_final_budget import FinalCitationBudgetResult
from medops.application.agent_final_gate import FinalGateConfig, check_structure, parse_material_check, policy_sha256
from medops.application.agent_tool_ports import AgentToolFault
from medops.core.canonical import canonical_hash, sha256_hex
from medops.domain.agent_actions import AgentModel, FinishAction, Key, NarrativeFact
from medops.domain.agent_execution import AgentBinding, AgentContext, BoundAction, EvidenceHandle, StopReason
from medops.domain.common import DISCLAIMER, Sha256
from medops.domain.evidence import Citation
from medops.domain.safety import SafetyDecision
from medops.domain.verification import Verdict
from medops.safety.checks import check_output_text

REVIEW_VERSION: Final = "pv-review-material-v1"
ItemState = Literal["verified", "missing", "incomplete", "not_supported", "contradicted", "withheld"]


class RequirementReview(AgentModel):
    requirement_id: Key
    kind: Literal["narrative", "guideline"]
    required: Annotated[bool, Field(strict=True)]
    state: ItemState


class GuidelineReview(AgentModel):
    claim_index: Annotated[int, Field(ge=0, le=31, strict=True)]
    requirement_id: Key
    text: str = Field(min_length=1, max_length=2000)
    # AND within each jointly necessary bundle, OR across independent alternatives.
    support_groups: tuple[tuple[UUID, ...], ...] = Field(min_length=1, max_length=8)


class ReviewEvidence(AgentModel):
    handle: UUID
    citation: Citation
    text: str = Field(min_length=1)
    evidence_text_sha256: Sha256
    source_sha256: Sha256

    @model_validator(mode="after")
    def content_digest(self) -> "ReviewEvidence":
        if sha256_hex(self.text) != self.evidence_text_sha256:
            raise ValueError("invalid_review_evidence")
        return self


class ReviewGates(AgentModel):
    narrative_supported: Literal["pass", "fail", "not_run"]
    requirements_complete: Literal["pass", "fail", "not_run"]
    scope_safe: Literal["pass", "fail", "not_run"]
    citations_supported: Literal["pass", "fail", "not_run"]


class PreparedReview(AgentModel):
    version: Literal["pv-review-material-v1"]
    binding: AgentBinding
    action_id: UUID
    draft_sha256: Sha256
    policy_sha256: Sha256
    gates: ReviewGates
    completion_eligible: Annotated[bool, Field(strict=True)]
    reason: StopReason
    disclaimer: Literal["基于文档检索，仅供专业人员参考"]
    requirements: tuple[RequirementReview, ...] = Field(min_length=1, max_length=32)
    narrative_facts: tuple[NarrativeFact, ...] = Field(max_length=64)
    guideline_claims: tuple[GuidelineReview, ...] = Field(max_length=32)
    evidence: tuple[ReviewEvidence, ...] = Field(max_length=64)
    call_receipt_ids: tuple[str, ...] = Field(max_length=64)

    @model_validator(mode="after")
    def consistent(self) -> "PreparedReview":
        if (
            (self.reason == "completed") != self.completion_eligible
            or len({r.requirement_id for r in self.requirements}) != len(self.requirements)
            or len({c.claim_index for c in self.guideline_claims}) != len(self.guideline_claims)
            or len(set(self.call_receipt_ids)) != len(self.call_receipt_ids)
        ):
            raise ValueError("invalid_prepared_review")
        if self.completion_eligible and (
            not self.call_receipt_ids
            or any(v != "pass" for v in self.gates.model_dump().values())
            or any(r.required and r.state != "verified" for r in self.requirements)
        ):
            raise ValueError("invalid_prepared_review")
        return self


def compile_review(
    context: AgentContext,
    action: BoundAction,
    registry: tuple[EvidenceHandle, ...],
    proof: FinalCitationBudgetResult,
    config: FinalGateConfig,
) -> PreparedReview:
    """Not a proof verifier for untrusted callers: the driver owns every input."""
    if not isinstance(action.proposal, FinishAction):
        raise AgentToolFault("dependency_error")
    draft = action.proposal.draft
    check_structure(context, draft)
    binding = context_binding(context)
    digest = canonical_hash(draft.model_dump(mode="json"))
    material = proof.material_check
    if (
        proof.binding != binding
        or action.binding != binding
        or proof.action_id != action.action_id
        or proof.draft_sha256 != digest
        or material is None
        or material.draft_sha256 != digest
        or material.policy_sha256 != policy_sha256(config)
        or not proof.call_receipt_ids
        or len(set(proof.call_receipt_ids)) != len(proof.call_receipt_ids)
    ):
        raise AgentToolFault("dependency_error")
    original = proof.payload.checks if proof.payload else ()
    if len(original) != len(draft.guideline_claims):
        raise AgentToolFault("dependency_error")
    for claim, check in zip(draft.guideline_claims, original, strict=True):
        if (claim.requirement_id, claim.text, claim.evidence_handles) != (
            check.requirement_id,
            check.text,
            check.requested_handles,
        ):
            raise AgentToolFault("dependency_error")
    actual = parse_material_check(
        material.verdict.model_dump(mode="json"),
        context,
        draft,
        config,
        original_citations_supported=all(c.verdict is Verdict.supported for c in original),
    )
    if actual != material:
        raise AgentToolFault("dependency_error")
    by_handle = {h.handle: h for h in registry}
    wanted = {h for c in draft.guideline_claims for h in c.evidence_handles}
    allowed = {(s.doc_id, s.version, s.source_sha256) for s in context.source_scope.allowed_sources}
    if len(by_handle) != len(registry) or not wanted <= by_handle.keys():
        raise AgentToolFault("denied_or_unavailable")
    for handle in wanted:
        row = by_handle[handle]
        if (
            row.binding != binding
            or (row.evidence.citation.doc_id, row.evidence.citation.version, row.source_sha256) not in allowed
        ):
            raise AgentToolFault("denied_or_unavailable")
    checks = {c.claim_index: c for c in material.verdict.guideline_support}
    semantic = {r.requirement_id: r.complete for r in material.verdict.requirements}
    # No unsafe/unsupported model text is copied as a fallback answer. Partial
    # facts may remain reviewable only if their separate whole-class checks pass.
    safe = (
        material.verdict.scope_safe
        and check_output_text(
            [f.value for f in draft.narrative_facts] + [c.text for c in draft.guideline_claims]
        ).decision
        is SafetyDecision.allow
    )
    narrative = draft.narrative_facts if safe and material.verdict.narrative_supported else ()
    guidelines = tuple(
        GuidelineReview(
            claim_index=i, requirement_id=c.requirement_id, text=c.text, support_groups=checks[i].support_groups
        )
        for i, c in enumerate(draft.guideline_claims)
        if safe and checks[i].verdict is Verdict.supported and original[i].verdict is Verdict.supported
    )
    items = []
    for r in context.requirements:
        raw_rows = (
            tuple(f for f in draft.narrative_facts if f.requirement_id == r.requirement_id)
            if r.kind == "narrative"
            else tuple(c for c in draft.guideline_claims if c.requirement_id == r.requirement_id)
        )
        supported_rows = (
            tuple(f for f in narrative if f.requirement_id == r.requirement_id)
            if r.kind == "narrative"
            else tuple(c for c in guidelines if c.requirement_id == r.requirement_id)
        )
        conflict = r.kind == "guideline" and any(
            original[i].verdict is Verdict.contradicted or checks[i].verdict is Verdict.contradicted
            for i, c in enumerate(draft.guideline_claims)
            if c.requirement_id == r.requirement_id
        )
        state: ItemState = (
            "withheld"
            if not safe
            else "missing"
            if not raw_rows
            else "contradicted"
            if conflict
            else "not_supported"
            if len(supported_rows) != len(raw_rows)
            else "incomplete"
            if not semantic[r.requirement_id]
            else "verified"
        )
        items.append(RequirementReview(requirement_id=r.requirement_id, kind=r.kind, required=r.required, state=state))
    eligible = (
        safe
        and material.semantic_supported
        and material.citations_supported
        and all(r.state == "verified" for r in items if r.required)
    )
    used = tuple(dict.fromkeys(h for c in guidelines for g in c.support_groups for h in g))
    evidence = tuple(
        ReviewEvidence(
            handle=h,
            citation=by_handle[h].evidence.citation,
            text=by_handle[h].evidence.text,
            evidence_text_sha256=by_handle[h].evidence.evidence_text_hash,
            source_sha256=by_handle[h].source_sha256,
        )
        for h in used
    )
    return PreparedReview(
        version=REVIEW_VERSION,
        binding=binding,
        action_id=action.action_id,
        draft_sha256=digest,
        policy_sha256=material.policy_sha256,
        gates=ReviewGates(
            narrative_supported="pass" if material.verdict.narrative_supported else "fail",
            requirements_complete="pass" if material.requirements_complete else "fail",
            scope_safe="pass" if safe else "fail",
            citations_supported="pass" if material.citations_supported else "fail",
        ),
        completion_eligible=eligible,
        reason=(
            "completed"
            if eligible
            else "safety_boundary"
            if not safe
            else "insufficient_evidence"
            if not material.citations_supported
            else "unsupported_requirement"
        ),
        disclaimer=DISCLAIMER,
        requirements=tuple(items),
        narrative_facts=narrative,
        guideline_claims=guidelines,
        evidence=evidence,
        call_receipt_ids=proof.call_receipt_ids,
    )


def structure_rejection(context: AgentContext, action: BoundAction, config: FinalGateConfig) -> PreparedReview:
    """No semantic verdicts or model text when the finish draft is incomplete."""
    if not isinstance(action.proposal, FinishAction) or action.binding != context_binding(context):
        raise AgentToolFault("dependency_error")
    draft = action.proposal.draft
    present = {f.requirement_id for f in draft.narrative_facts} | {c.requirement_id for c in draft.guideline_claims}
    return PreparedReview(
        version=REVIEW_VERSION,
        binding=action.binding,
        action_id=action.action_id,
        draft_sha256=canonical_hash(draft.model_dump(mode="json")),
        policy_sha256=policy_sha256(config),
        gates=ReviewGates(
            narrative_supported="not_run",
            requirements_complete="fail",
            scope_safe="not_run",
            citations_supported="not_run",
        ),
        completion_eligible=False,
        reason="unsupported_requirement",
        disclaimer=DISCLAIMER,
        requirements=tuple(
            RequirementReview(
                requirement_id=r.requirement_id,
                kind=r.kind,
                required=r.required,
                state="withheld" if r.requirement_id in present else "missing",
            )
            for r in context.requirements
        ),
        narrative_facts=(),
        guideline_claims=(),
        evidence=(),
        call_receipt_ids=(),
    )


def validate_review_binding(
    review: PreparedReview,
    context: AgentContext,
    action: BoundAction,
    registry: tuple[EvidenceHandle, ...],
    config: FinalGateConfig,
) -> None:
    """Binding/visible-content checks for an authenticated committed review replay."""
    if not isinstance(action.proposal, FinishAction):
        raise AgentToolFault("dependency_error")
    draft = action.proposal.draft
    if (
        review.binding != context_binding(context)
        or review.action_id != action.action_id
        or review.draft_sha256 != canonical_hash(draft.model_dump(mode="json"))
        or review.policy_sha256 != policy_sha256(config)
        or [(r.requirement_id, r.kind, r.required) for r in review.requirements]
        != [(r.requirement_id, r.kind, r.required) for r in context.requirements]
        or any(f not in draft.narrative_facts for f in review.narrative_facts)
    ):
        raise AgentToolFault("dependency_error")
    by_handle = {h.handle: h for h in registry}
    used = {h for c in review.guideline_claims for g in c.support_groups for h in g}
    if used != {e.handle for e in review.evidence} or len({e.handle for e in review.evidence}) != len(review.evidence):
        raise AgentToolFault("dependency_error")
    for row in review.guideline_claims:
        if row.claim_index >= len(draft.guideline_claims):
            raise AgentToolFault("dependency_error")
        claim = draft.guideline_claims[row.claim_index]
        if (row.requirement_id, row.text) != (claim.requirement_id, claim.text) or any(
            not set(g) <= set(claim.evidence_handles) for g in row.support_groups
        ):
            raise AgentToolFault("dependency_error")
    for evidence_row in review.evidence:
        actual = by_handle.get(evidence_row.handle)
        if actual is None or (
            evidence_row.citation,
            evidence_row.text,
            evidence_row.evidence_text_sha256,
            evidence_row.source_sha256,
        ) != (
            actual.evidence.citation,
            actual.evidence.text,
            actual.evidence.evidence_text_hash,
            actual.source_sha256,
        ):
            raise AgentToolFault("denied_or_unavailable")
