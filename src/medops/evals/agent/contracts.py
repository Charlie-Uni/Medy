"""Closed evaluator inputs; hashes bind bytes, not an assessor's authenticity.

Expectations and assessments belong to a trusted evaluation process. Passing a
JSON record does not prove its truth. No planner or tool may supply verdicts.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, TypeVar

from pydantic import Field, field_validator, model_validator

from medops.core.canonical import canonical_hash
from medops.domain.agent_execution import AgentStatus, StopReason
from medops.domain.common import DomainModel, NonEmptyStr, Sha256

T = TypeVar("T", bound=DomainModel)

RUBRIC_VERSION: Literal["pv-agent-rubric-v1"] = "pv-agent-rubric-v1"
Verdict = Literal["pass", "fail", "unknown", "not_applicable"]
Count = Annotated[int, Field(ge=0, strict=True)]
GUARDS = (
    "authorization",
    "input_safety",
    "output_safety",
    "budget",
    "deadline",
    "cancellation",
    "ownership",
    "version_binding",
    "audit",
    "fee_reconciliation",
)


class Requirement(DomainModel):
    requirement_id: NonEmptyStr
    kind: Literal["narrative", "guideline"]
    # AND across groups, OR inside each group. IDs are evidence identities,
    # not search rank, source title, or arbitrary model-generated labels.
    evidence_groups: tuple[tuple[NonEmptyStr, ...], ...] = ()

    @model_validator(mode="after")
    def groups(self) -> Requirement:
        if (self.kind == "guideline") != bool(self.evidence_groups):
            raise ValueError("invalid_evidence_groups")
        if any(not g or len(g) != len(set(g)) for g in self.evidence_groups):
            raise ValueError("invalid_evidence_groups")
        return self


TerminalStatus = Literal["awaiting_clarification", "completed", "escalated", "failed", "cancelled"]


class TaskSpec(DomainModel):
    execution_id: NonEmptyStr
    business_case_id: NonEmptyStr
    scenario_id: NonEmptyStr
    variant: NonEmptyStr
    parent_execution_id: NonEmptyStr | None = None
    expected_status: TerminalStatus
    expected_reason: StopReason
    narrative: NonEmptyStr
    question: NonEmptyStr
    requested_document: NonEmptyStr
    requested_version: NonEmptyStr | None
    as_of: date | None = None
    historical: bool = Field(default=False, strict=True)
    requirements: tuple[Requirement, ...] = Field(min_length=1)
    allowed_source_ids: tuple[NonEmptyStr, ...] = ()
    tool_free_safety_block: bool = Field(default=False, strict=True)
    recovery_required: bool = Field(default=False, strict=True)
    # Fixed before execution. These are evaluator checks, not model assertions.
    behavior_checks: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique(self) -> TaskSpec:
        for values in (
            [r.requirement_id for r in self.requirements],
            self.allowed_source_ids,
            self.behavior_checks,
        ):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_expectation")
        return self


class EvaluationPlan(DomainModel):
    format: Literal["pv-agent-evaluation-plan-v1"] = "pv-agent-evaluation-plan-v1"
    rubric_version: Literal["pv-agent-rubric-v1"] = RUBRIC_VERSION
    usage: Literal["development_only"] = "development_only"
    unseen_holdout: Literal[False] = False
    medical_gold: Literal[False] = False
    engineering_scripts_only: Literal[True] = True
    historical_spec_sha256: Sha256
    approved_contract_sha256: Sha256
    execution_conditions_sha256: Sha256
    tasks: tuple[TaskSpec, ...] = Field(min_length=1, max_length=10000)

    @field_validator("unseen_holdout", "medical_gold", "engineering_scripts_only", mode="before")
    @classmethod
    def explicit_boolean(cls, value: object) -> object:
        if type(value) is not bool:
            raise ValueError("invalid_boolean")
        return value

    @model_validator(mode="after")
    def registered_roster(self) -> EvaluationPlan:
        seen: dict[str, TaskSpec] = {}
        roots: set[str] = set()
        for task in self.tasks:
            if task.execution_id in seen:
                raise ValueError("duplicate_execution")
            if task.parent_execution_id:
                parent = seen.get(task.parent_execution_id)
                if parent is None or parent.business_case_id != task.business_case_id:
                    raise ValueError("invalid_followup")
            else:
                if task.business_case_id in roots:
                    raise ValueError("duplicate_case_root")
                roots.add(task.business_case_id)
            seen[task.execution_id] = task
        return self


class Fact(DomainModel):
    item_id: NonEmptyStr
    requirement_id: NonEmptyStr
    value: NonEmptyStr
    quote: NonEmptyStr
    char_start: Count
    char_end: Count


class Claim(DomainModel):
    item_id: NonEmptyStr
    requirement_id: NonEmptyStr
    text: NonEmptyStr
    cited_evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class EvidenceRecord(DomainModel):
    evidence_id: NonEmptyStr
    source_id: NonEmptyStr
    text: NonEmptyStr


class ActionRecord(DomainModel):
    action_id: NonEmptyStr
    # None represents a malformed planner response; it still consumes a decision.
    action: (
        Literal["extract_ae", "search_documents", "read_evidence", "verify_citations", "clarify", "finish", "escalate"]
        | None
    )
    query: NonEmptyStr | None = None
    read_region: Literal["current", "previous", "next"] | None = None
    parameters_sha256: Sha256
    result: NonEmptyStr
    result_sha256: Sha256
    new_evidence_ids: tuple[NonEmptyStr, ...] = ()


class Usage(DomainModel):
    model_attempts: Count
    input_tokens: Count
    output_tokens: Count
    known_cost_microusd: Count
    conservative_cost_microusd: Count
    elapsed_ms: Count
    waiting_ms: Count
    cleanup_ms: Count


class ExecutionRecord(DomainModel):
    execution_id: NonEmptyStr
    plan_sha256: Sha256
    execution_conditions_sha256: Sha256
    status: AgentStatus
    reason: StopReason | None
    facts: tuple[Fact, ...] = ()
    claims: tuple[Claim, ...] = ()
    evidence: tuple[EvidenceRecord, ...] = ()
    actions: tuple[ActionRecord, ...] = ()
    saved_material_sha256: Sha256 | None = None
    usage: Usage
    # Digest of durable restricted trace/receipts, not unrestricted prompt text.
    audit_sha256: Sha256

    @model_validator(mode="after")
    def unique(self) -> ExecutionRecord:
        for values in (
            [f.item_id for f in self.facts] + [c.item_id for c in self.claims],
            [e.evidence_id for e in self.evidence],
            [a.action_id for a in self.actions],
        ):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_observation")
        return self


class Check(DomainModel):
    key: NonEmptyStr
    verdict: Literal["pass", "fail", "unknown"]
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)


class JudgeAttempt(DomainModel):
    attempt_id: NonEmptyStr
    receipt_ref: NonEmptyStr
    status: Literal["completed", "failed", "cancelled"]
    usage: Usage


class Assessment(DomainModel):
    """Restricted evaluator annotation over exact record bytes.

    Checks use fixed keys: guard:<name>, behavior:<registered name>, tool:<action>,
    fact:<item>, claim:<item>, citation:<item>:<evidence>, stop, recovery.
    Missing keys are unknown. A failed judge keeps its ID/error in evidence_refs.
    """

    execution_id: NonEmptyStr
    record_sha256: Sha256
    rubric_version: Literal["pv-agent-rubric-v1"] = RUBRIC_VERSION
    assessor: Literal["scripted_fixture", "human", "model_judge"]
    assessor_id: NonEmptyStr
    checks: tuple[Check, ...]
    judge_attempts: tuple[JudgeAttempt, ...] = ()

    @model_validator(mode="after")
    def unique(self) -> Assessment:
        keys = [c.key for c in self.checks]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_check")
        attempts = [a.attempt_id for a in self.judge_attempts]
        if len(attempts) != len(set(attempts)):
            raise ValueError("duplicate_judge_attempt")
        if self.assessor == "model_judge" and not attempts:
            raise ValueError("missing_judge_receipts")
        return self


def digest(value: DomainModel) -> str:
    return canonical_hash(value.model_dump(mode="json"))


def revalidate(value: T) -> T:
    # model_copy(update=...) bypasses validation; never trust an instance boundary.
    return type(value).model_validate(value.model_dump(mode="python", warnings=False))
