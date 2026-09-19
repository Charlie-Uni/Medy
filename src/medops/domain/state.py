"""AgentState: the only channel between harness nodes (design 3.2, INV-HAR-02/03, INV-HAR-08).

The state is immutable; a node produces the next state with `advance(...)`, which re-validates
every cross-field invariant. Nothing here executes retrieval, verification or safety; the
model only makes illegal combinations unrepresentable.
"""

from __future__ import annotations

from pydantic import Field, TypeAdapter, field_validator, model_validator

from medops.domain.answer import Answer, Escalation
from medops.domain.common import DomainModel, NonEmptyStr
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.intent import Entity, Intent, IntentType
from medops.domain.safety import SafetyDecision, SafetyResult
from medops.domain.verification import VerifyResult

MAX_REWRITTEN_QUERIES = 3  # baseline 5.2: 1-3 bounded queries
MAX_CANDIDATES = 20  # baseline 4.4: reranker input at most 20
MAX_EVIDENCE = 8  # baseline 4.4: at most 8 evidence fragments in context


class VersionSet(DomainModel):
    """Every version that shapes a run; recorded on each trace (INV-HAR-05) and inside operation keys."""

    policy_version: NonEmptyStr
    retrieval_version: NonEmptyStr
    skill_version_set: tuple[NonEmptyStr, ...] = ()
    model_config_version: NonEmptyStr

    @field_validator("skill_version_set")
    @classmethod
    def _sorted_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """A set by contract: stored sorted and de-duplicated so hashes do not depend on input order."""
        return tuple(sorted(set(value)))


class TokenBudget(DomainModel):
    limit: int = Field(gt=0)
    used: int = Field(ge=0)

    @model_validator(mode="after")
    def _within_limit(self) -> TokenBudget:
        if self.used > self.limit:
            raise ValueError("token budget exceeded; trim evidence or escalate (INV-HAR-08)")
        return self

    @property
    def remaining(self) -> int:
        return self.limit - self.used


class SourceRank(DomainModel):
    source: NonEmptyStr
    rank: int = Field(ge=1)


class CandidateRef(DomainModel):
    """A fused, not yet rechecked candidate (design: candidates are never facts)."""

    chunk_id: NonEmptyStr
    source_ranks: tuple[SourceRank, ...] = Field(min_length=1)

    @field_validator("source_ranks")
    @classmethod
    def _unique_sources(cls, value: tuple[SourceRank, ...]) -> tuple[SourceRank, ...]:
        if len({r.source for r in value}) != len(value):
            raise ValueError("each source may contribute one rank per candidate")
        return value


class AgentState(DomainModel):
    trace_id: NonEmptyStr
    run_id: NonEmptyStr  # == trace_id in production, a separate replay_run_id for replays (baseline 3.2)
    user: UserContext
    query: NonEmptyStr
    versions: VersionSet
    budget: TokenBudget
    session_entities: tuple[Entity, ...] = ()
    historical_requested: bool = False
    intent: Intent | None = None
    rewritten_queries: tuple[NonEmptyStr, ...] = Field(default=(), max_length=MAX_REWRITTEN_QUERIES)
    candidates: tuple[CandidateRef, ...] = Field(default=(), max_length=MAX_CANDIDATES)
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=MAX_EVIDENCE)
    verify_result: VerifyResult | None = None
    safety_result: SafetyResult | None = None
    answer: Answer | None = None
    escalation: Escalation | None = None

    @model_validator(mode="after")
    def _invariants(self) -> AgentState:
        chunk_ids = [e.citation.chunk_id for e in self.evidence]
        if len(set(chunk_ids)) != len(chunk_ids):
            raise ValueError("evidence chunk ids must be unique")
        if any(e.historical for e in self.evidence) and not self.historical_requested:
            raise ValueError("historical evidence requires an explicit historical request (INV-DATA-03)")
        if self.verify_result is not None:
            referenced = {e.evidence_chunk_id for e in self.verify_result.elements if e.evidence_chunk_id}
            if not referenced <= set(chunk_ids):
                raise ValueError(
                    f"verify_result references chunks outside evidence: {sorted(referenced - set(chunk_ids))}"
                )
        if self.escalation is not None and not set(self.escalation.evidence_chunk_ids) <= set(chunk_ids):
            raise ValueError("escalation references evidence chunks that are not in this state")
        if self.answer is not None and self.escalation is not None:
            raise ValueError("a run ends with either an answer or an escalation, never both")
        if self.answer is not None:
            self._answer_gate()
        if self.escalation is not None and self.escalation.policy_version != self.versions.policy_version:
            raise ValueError("escalation policy_version must match the run's policy_version")
        return self

    def _answer_gate(self) -> None:
        """INV-HAR-03 / INV-SAF-01 / INV-SAF-03 / INV-SAF-05: an answer is only representable after intent,
        evidence, verification and safety all exist and agree."""
        assert self.answer is not None
        if self.intent is None:
            raise ValueError("an answer requires a classified intent")
        if self.intent.type is IntentType.high_risk:
            raise ValueError("high-risk intents are refused and escalated, never answered (INV-SAF-01)")
        if not self.evidence:
            raise ValueError("an answer requires verified evidence (INV-HAR-03)")
        vr = self.verify_result
        if vr is None or not vr.structural_ok or vr.contradicted:
            raise ValueError("an answer requires a passing, non-contradicted verify_result")
        if vr.unsupported:
            raise ValueError("an answer cannot keep not_supported elements; drop them and re-verify (baseline 3.5)")
        if self.safety_result is None or self.safety_result.decision is not SafetyDecision.allow:
            raise ValueError("an answer requires safety decision allow (INV-SAF-05)")
        verified = {e.citation for e in self.evidence}
        forged = [c for c in self.answer.citations if c not in verified]
        if forged:
            raise ValueError(
                f"answer citations must equal verified evidence citations field by field: {[c.chunk_id for c in forged]}"
            )
        if self.answer.historical_notice != any(e.historical for e in self.evidence):
            raise ValueError("historical_notice must reflect whether historical evidence was used")

    def advance(self, **updates: object) -> AgentState:
        """Return the next state with `updates` applied and all invariants re-validated.

        Downstream results never outlive the inputs they were computed from: when an upstream field
        actually changes, every downstream field not supplied in the same call is reset (fixed table
        below, no dependency framework). Change detection compares typed values, so a model object,
        a dict or a list that validates to the same value is not a change. A downstream value passed
        in the same call is a trusted caller's declaration that it was recomputed; it is not proof that
        verification ran, which is enforced by the M2 runtime, not by this model."""
        typed_updates = {field: _ADAPTERS[field].validate_python(value) for field, value in updates.items()}
        merged: dict[str, object] = {**self.model_dump(), **typed_updates}
        for field, downstream in _DOWNSTREAM.items():
            if field in typed_updates and typed_updates[field] != getattr(self, field):
                for dep in downstream:
                    if dep not in updates:
                        merged[dep] = _EMPTY[dep]
        return AgentState.model_validate(merged)


_EMPTY: dict[str, object] = {
    "intent": None,
    "rewritten_queries": (),
    "candidates": (),
    "evidence": (),
    "verify_result": None,
    "safety_result": None,
    "answer": None,
    "escalation": None,
}
_ALL_RESULTS = (
    "intent",
    "rewritten_queries",
    "candidates",
    "evidence",
    "verify_result",
    "safety_result",
    "answer",
    "escalation",
)
_DOWNSTREAM: dict[str, tuple[str, ...]] = {
    "query": _ALL_RESULTS,
    "user": _ALL_RESULTS,
    "versions": _ALL_RESULTS,
    "session_entities": _ALL_RESULTS,  # intent extraction and query rewriting both read them
    "historical_requested": ("candidates", "evidence", "verify_result", "safety_result", "answer", "escalation"),
    "intent": ("rewritten_queries", "candidates", "evidence", "verify_result", "safety_result", "answer", "escalation"),
    "rewritten_queries": ("candidates", "evidence", "verify_result", "safety_result", "answer", "escalation"),
    "candidates": ("evidence", "verify_result", "safety_result", "answer", "escalation"),
    "evidence": ("verify_result", "safety_result", "answer", "escalation"),
    "verify_result": ("safety_result", "answer", "escalation"),
    "safety_result": ("answer", "escalation"),
}
_ADAPTERS: dict[str, TypeAdapter[object]] = {
    name: TypeAdapter(info.annotation) for name, info in AgentState.model_fields.items()
}
