"""Bridges to the two existing PV Skills; no new model prompts or retry layer."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

from medops.application.agent_tool_ports import AgentFacts, AgentToolFault
from medops.application.agent_tool_results import (
    AgentFact,
    ClaimToolCheck,
    ExtractedElement,
    ExtractionPayload,
    VerificationPayload,
)
from medops.core.canonical import canonical_hash
from medops.core.deadline import DeadlineExceeded
from medops.core.errors import ErrorCode
from medops.domain.agent_actions import VerifyCitationsAction
from medops.domain.agent_execution import AgentContext, EvidenceHandle
from medops.domain.answer import Claim
from medops.domain.common import ReasonCode
from medops.domain.skill import SkillStatus
from medops.domain.verification import Verdict
from medops.harness.contracts import MAX_RETRIES
from medops.infrastructure.llm.call_plan import ModelCallPlan
from medops.infrastructure.llm.gateway import BudgetExceeded, ModelRequest
from medops.safety.checks import screen_evidence
from medops.skills import ae_extraction, citation_verification
from medops.skills.registry import SkillContext, SkillRegistry, SkillRun
from medops.verification.verifier import plan_claim_judges


def _skill_ok(result: SkillRun) -> None:
    if ReasonCode.budget_exceeded in result.output.reason_codes:
        raise BudgetExceeded("agent_tool_budget")
    if result.attempts and (
        result.attempts[-1].outcome == "timeout" or result.attempts[-1].error_code == ErrorCode.dependency_timeout.value
    ):
        raise DeadlineExceeded()
    if ReasonCode.system_failure in result.output.reason_codes:
        raise AgentToolFault("dependency_error")
    if result.output.status is SkillStatus.escalated:
        raise AgentToolFault("unsupported")


class PVSkillAdapter:
    """Registry-owned adapter. All model work still enters Registry.execute."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def contract_sha256(self) -> str:
        return canonical_hash(
            [
                {
                    "spec": e.spec.model_dump(mode="json"),
                    "input": e.input_model.model_json_schema(),
                    "output": e.output_model.model_json_schema(),
                }
                for e in (ae_extraction.ENTRY, citation_verification.ENTRY)
            ]
        )

    def validate_versions(self, versions: tuple[str, ...]) -> None:
        for expected in (ae_extraction.ENTRY, citation_verification.ENTRY):
            actual = self.registry.get(expected.spec.name, expected.spec.version)
            if (
                actual.spec != expected.spec
                or actual.input_model != expected.input_model
                or actual.output_model != expected.output_model
                or (actual.handler is not expected.handler)
                or (expected.spec.version_tag not in versions)
            ):
                raise AgentToolFault("dependency_error")

    def extract(
        self, context: AgentContext, skill_context: SkillContext
    ) -> tuple[ExtractionPayload, tuple[EvidenceHandle, ...], tuple[AgentFact, ...]]:
        result = self.registry.execute(
            "ae_extraction",
            "1.0.0",
            {"narrative": context.narrative, "source_type": context.source_type},
            context=skill_context,
        )
        _skill_ok(result)
        out = result.output
        if not isinstance(out, ae_extraction.AeExtractionOutput):
            raise AgentToolFault("dependency_error")
        elements = []
        unaligned = 0
        for element in out.elements:
            start = context.narrative.find(element.quote)
            if start < 0 or context.narrative.find(element.quote, start + 1) >= 0:
                unaligned += 1
                continue
            elements.append(
                ExtractedElement(
                    kind=element.kind,
                    value=element.value,
                    quote=element.quote,
                    char_start=start,
                    char_end=start + len(element.quote),
                )
            )
        found = {e.kind for e in elements}
        return (
            ExtractionPayload(
                skill_status=out.status,
                elements=tuple(elements),
                missing_kinds=tuple(k for k in ae_extraction.KINDS if k not in found),
                unaligned_elements=unaligned,
                dropped_ungrounded=out.dropped_ungrounded,
                dropped_causality=out.dropped_causality,
            ),
            (),
            (),
        )

    def plan_extract(self, context: AgentContext, skill_context: SkillContext) -> ModelCallPlan:
        inp = ae_extraction.AeExtractionInput(narrative=context.narrative, source_type=context.source_type)
        return ModelCallPlan(
            requests=(ae_extraction.budget_request(skill_context, inp),),
            max_attempts=1 + (MAX_RETRIES if ae_extraction.SPEC.idempotent else 0),
        )

    def plan_verify(
        self,
        proposal: VerifyCitationsAction,
        context: AgentContext,
        registry: dict[UUID, EvidenceHandle],
        skill_context: SkillContext,
        facts_port: AgentFacts,
    ) -> ModelCallPlan:
        facts = self._verification_facts(proposal, context, registry, facts_port)
        visible, _ = screen_evidence(tuple(f.evidence for f in facts))
        by_id = {e.citation.chunk_id: e for e in visible}
        requests: list[ModelRequest] = []
        for item in proposal.claims:
            known = tuple(
                registry[h].evidence.citation.chunk_id
                for h in item.evidence_handles
                if registry[h].evidence.citation.chunk_id in by_id
            )
            if known:
                requests.extend(
                    plan_claim_judges(
                        [Claim(text=item.text, citation_chunk_ids=known)],
                        [by_id[c] for c in known],
                        judge_model_id=skill_context.deps.judge_model_id,
                        timeout_s=skill_context.deps.specs["verify"].timeout_s,
                    )
                )
        return ModelCallPlan(
            requests=tuple(requests),
            max_attempts=1 + (MAX_RETRIES if citation_verification.SPEC.idempotent else 0),
        )

    def _verification_facts(
        self,
        proposal: VerifyCitationsAction,
        context: AgentContext,
        registry: dict[UUID, EvidenceHandle],
        facts_port: AgentFacts,
    ) -> tuple[AgentFact, ...]:
        if len(proposal.claims) > citation_verification.MAX_CLAIMS or any(len(c.text) > 1000 for c in proposal.claims):
            raise AgentToolFault("unsupported")
        wanted = tuple(
            dict.fromkeys(registry[h].evidence.citation.chunk_id for c in proposal.claims for h in c.evidence_handles)
        )
        facts = facts_port.lookup(context, wanted)
        expected = {
            registry[h].evidence.citation.chunk_id: AgentFact(
                evidence=registry[h].evidence, source_sha256=registry[h].source_sha256
            )
            for c in proposal.claims
            for h in c.evidence_handles
        }
        if {f.evidence.citation.chunk_id: f for f in facts} != expected:
            raise AgentToolFault("denied_or_unavailable")
        return facts

    def verify(
        self,
        proposal: VerifyCitationsAction,
        context: AgentContext,
        registry: dict[UUID, EvidenceHandle],
        skill_context: SkillContext,
        facts_port: AgentFacts,
    ) -> tuple[VerificationPayload, tuple[EvidenceHandle, ...], tuple[AgentFact, ...]]:
        facts = self._verification_facts(proposal, context, registry, facts_port)
        by_id = {f.evidence.citation.chunk_id: f.evidence for f in facts}

        def lookup(user, ids):
            if user != context.principal or not set(ids) <= by_id.keys():
                raise AgentToolFault("denied_or_unavailable")
            return tuple(f.evidence for f in facts_port.lookup(context, tuple(ids)))

        verifying_context = replace(skill_context, evidence_lookup=lookup)
        raw = {
            "claims": [
                {
                    "text": c.text,
                    "citation_chunk_ids": tuple(registry[h].evidence.citation.chunk_id for h in c.evidence_handles),
                }
                for c in proposal.claims
            ]
        }
        result = self.registry.execute("citation_verification", "1.0.0", raw, context=verifying_context)
        _skill_ok(result)
        out = result.output
        if not isinstance(out, citation_verification.CitationVerificationOutput) or len(out.verdicts) != len(
            proposal.claims
        ):
            raise AgentToolFault("dependency_error")
        checks = []
        for claim, verdict in zip(proposal.claims, out.verdicts, strict=True):
            if verdict.text != claim.text or any(
                s.chunk_id not in by_id or by_id[s.chunk_id].citation != s for s in verdict.sources
            ):
                raise AgentToolFault("dependency_error")
            source_ids = {s.chunk_id for s in verdict.sources}
            wanted_for_claim = {registry[h].evidence.citation.chunk_id for h in claim.evidence_handles}
            if (
                not source_ids <= wanted_for_claim
                or verdict.unknown_citations
                or (verdict.verdict is Verdict.supported and (not source_ids))
            ):
                raise AgentToolFault("dependency_error")
            supporting = tuple(
                h for h in claim.evidence_handles if registry[h].evidence.citation.chunk_id in source_ids
            )
            checks.append(
                ClaimToolCheck(
                    requirement_id=claim.requirement_id,
                    text=claim.text,
                    verdict=verdict.verdict,
                    requested_handles=claim.evidence_handles,
                    supporting_handles=supporting,
                    unconfirmed_handles=tuple(h for h in claim.evidence_handles if h not in supporting),
                )
            )
        return (VerificationPayload(checks=tuple(checks), verifier_version=out.verifier_version), (), facts)
