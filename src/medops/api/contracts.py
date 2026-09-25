"""Public API contracts (baseline 5.7, M0-08): request/response models for the endpoints in the
design document (3.10). No server here. The OpenAPI 3.1 document is built from these same models by
`medops.api.openapi` and exported to `schemas/openapi.json`.

Outcomes are explicit: an ask either answers, refuses or escalates, never a mix, and refusals and
escalations always carry stable reason codes (F4.1). Answers reuse the domain `Answer`, so the fixed
disclaimer and claim-citation structure are the same on the wire as inside the harness.

Cross-field rules that JSON Schema can express (outcome/payload pairing, task terminal payloads,
historical selector, correction text) are also emitted into the exported schemas through
`json_schema_extra`, so a client validating against `schemas/` sees the same rejections as the
models. Rules that need server state (hash recomputation, authorization) stay server-side.
`extra="forbid"` applies to the fields of these models; query-parameter parsing and authentication
are implemented with the routes in M3.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from pydantic.config import JsonDict

from medops.core.errors import ErrorResponse
from medops.domain.answer import Answer
from medops.domain.common import Dept, ReasonCode
from medops.domain.state import VersionSet

TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
NonEmptyStr = Annotated[str, Field(min_length=1)]


class ApiModel(BaseModel):
    # allow_inf_nan=False: NaN/Infinity would serialize to null and change the request's meaning
    # (and canonical JSON forbids them, baseline 3.2).
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class HistoricalRequest(ApiModel):
    """Explicit request for an archived version (INV-DATA-03); exactly one selector."""

    model_config = ConfigDict(
        json_schema_extra={
            "oneOf": [
                {"required": ["version"], "properties": {"version": {"type": "string"}, "as_of": {"type": "null"}}},
                {"required": ["as_of"], "properties": {"as_of": {"type": "string"}, "version": {"type": "null"}}},
            ]
        }
    )

    version: NonEmptyStr | None = None
    as_of: date | None = None

    @model_validator(mode="after")
    def _one_selector(self) -> HistoricalRequest:
        if (self.version is None) == (self.as_of is None):
            raise ValueError("historical request needs exactly one of version or as_of")
        return self


class AskRequest(ApiModel):
    query: Annotated[str, Field(min_length=1, max_length=2000)]
    session_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    historical: HistoricalRequest | None = None


class OutcomeKind(StrEnum):
    answered = "answered"
    refused = "refused"
    escalated = "escalated"


class Refusal(ApiModel):
    reason_codes: tuple[ReasonCode, ...] = Field(min_length=1)
    message: NonEmptyStr


class EscalationReceipt(ApiModel):
    escalation_id: NonEmptyStr
    reason_codes: tuple[ReasonCode, ...] = Field(min_length=1)
    message: NonEmptyStr


def _outcome_rule(outcome: str, payload: str, others: tuple[str, ...]) -> JsonDict:
    props: JsonDict = {payload: {"type": "object"}}
    for other in others:
        props[other] = {"type": "null"}
    return {"if": {"properties": {"outcome": {"const": outcome}}}, "then": {"required": [payload], "properties": props}}


class AskResponse(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                _outcome_rule("answered", "answer", ("refusal", "escalation")),
                _outcome_rule("refused", "refusal", ("answer", "escalation")),
                _outcome_rule("escalated", "escalation", ("answer", "refusal")),
            ]
        }
    )

    trace_id: TraceId
    outcome: OutcomeKind
    versions: VersionSet
    answer: Answer | None = None
    refusal: Refusal | None = None
    escalation: EscalationReceipt | None = None

    @model_validator(mode="after")
    def _exactly_one_outcome_payload(self) -> AskResponse:
        present = {
            k
            for k, v in (("answered", self.answer), ("refused", self.refusal), ("escalated", self.escalation))
            if v is not None
        }
        if present != {self.outcome.value}:
            raise ValueError(f"outcome {self.outcome.value} requires exactly its own payload, found {sorted(present)}")
        return self


class TaskStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class TaskCreateRequest(ApiModel):
    """Skill workflow submission. `input` is validated against the skill's registered schema at
    execution time (M2-11); the wire contract only requires a finite JSON object."""

    skill_name: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")]
    skill_version: NonEmptyStr
    input: dict[str, JsonValue]
    historical: HistoricalRequest | None = None


class TaskResultStatus(StrEnum):
    completed = "completed"
    insufficient_evidence = "insufficient_evidence"
    escalated = "escalated"


class TaskResult(ApiModel):
    """Result of a skill task (M3-02): the skill's typed output as it was validated against the skill's registered
    output schema (`GET` the schema through the Registry's `describe`), plus the run status and reason codes.
    Skill outputs are structured per skill (AE elements, deviation findings, label excerpts), so they are not
    forced into the `AskResponse` shape."""

    skill: NonEmptyStr  # name@version, also recorded in `versions.skill_version_set`
    status: TaskResultStatus
    reason_codes: tuple[ReasonCode, ...] = ()
    output: dict[str, JsonValue]
    versions: VersionSet

    @model_validator(mode="after")
    def _non_completion_has_a_reason(self) -> TaskResult:
        if self.status is not TaskResultStatus.completed and not self.reason_codes:
            raise ValueError("a non-completed task result needs at least one reason code")
        return self


class TaskResponse(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"status": {"const": "completed"}}},
                    "then": {
                        "required": ["result"],
                        "properties": {"result": {"type": "object"}, "error": {"type": "null"}},
                    },
                },
                {
                    "if": {"properties": {"status": {"const": "failed"}}},
                    "then": {
                        "required": ["error"],
                        "properties": {"error": {"type": "object"}, "result": {"type": "null"}},
                    },
                },
                {
                    "if": {"properties": {"status": {"enum": ["queued", "running"]}}},
                    "then": {"properties": {"result": {"type": "null"}, "error": {"type": "null"}}},
                },
            ]
        }
    )

    task_id: NonEmptyStr
    status: TaskStatus
    trace_id: TraceId | None = None
    created_at: datetime
    updated_at: datetime
    result: TaskResult | None = None
    error: ErrorResponse | None = None

    @model_validator(mode="after")
    def _terminal_payloads(self) -> TaskResponse:
        has_result, has_error = self.result is not None, self.error is not None
        if self.status is TaskStatus.completed and not (has_result and not has_error):
            raise ValueError("completed tasks carry a result and no error")
        if self.status is TaskStatus.failed and not (has_error and not has_result):
            raise ValueError("failed tasks carry an error and no result")
        if self.status in (TaskStatus.queued, TaskStatus.running) and (has_result or has_error):
            raise ValueError("non-terminal tasks carry neither result nor error")
        return self


class FeedbackSignal(StrEnum):
    up = "up"
    down = "down"
    correction = "correction"


class FeedbackRequest(ApiModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"signal": {"const": "correction"}}},
                    "then": {"required": ["correction_text"], "properties": {"correction_text": {"type": "string"}}},
                },
                {
                    "if": {"properties": {"signal": {"enum": ["up", "down"]}}},
                    "then": {"properties": {"correction_text": {"type": "null"}}},
                },
            ]
        }
    )

    trace_id: TraceId
    signal: FeedbackSignal
    correction_text: Annotated[str, Field(min_length=1, max_length=4000)] | None = None

    @model_validator(mode="after")
    def _correction_needs_text(self) -> FeedbackRequest:
        if (self.signal is FeedbackSignal.correction) != (self.correction_text is not None):
            raise ValueError("correction_text is required for correction and forbidden otherwise")
        return self


class FeedbackReceipt(ApiModel):
    feedback_id: NonEmptyStr
    trace_id: TraceId


class ReplayRequest(ApiModel):
    """Admin request to re-run one trace (M3-08). The replay runs the original question under the original
    principal's current identity, with this deployment's pinned versions, under a fresh `replay_run_id` so no
    operation-key result of the production run can be reused."""

    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ReplaySide(ApiModel):
    trace_id: TraceId
    run_id: NonEmptyStr
    outcome: NonEmptyStr
    reason_codes: tuple[ReasonCode, ...] = ()
    cited_chunk_ids: tuple[str, ...] = ()
    evidence_chunk_ids: tuple[str, ...] = ()
    versions: VersionSet


class ReplayReport(ApiModel):
    replay_id: NonEmptyStr
    source: ReplaySide
    replay: ReplaySide
    versions_match: bool  # the source ran under exactly this deployment's version set
    changed: tuple[str, ...] = ()  # fields that differ between source and replay
    created_at: datetime


IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
"""POST /v1/tasks and POST /v1/feedback accept this header (baseline 3.2): scope is
authenticated principal + route + key; same key and payload returns the original receipt, also while
in progress; same key with a different payload returns 422 idempotency_payload_mismatch."""


# ------------------------------------------------------------------------------- admin: documents (M3-03, DEC-012)


class DocumentStatus(StrEnum):
    draft = "draft"
    active = "active"
    archived = "archived"
    withdrawn = "withdrawn"


class DocumentSummary(ApiModel):
    """Metadata only: admin views never return chunk content."""

    doc_id: NonEmptyStr
    document_key: NonEmptyStr
    family_id: NonEmptyStr
    title: NonEmptyStr
    doc_type: NonEmptyStr
    owner_dept: Dept
    status: DocumentStatus
    version: NonEmptyStr
    effective_from: date | None = None
    effective_to: date | None = None
    read_depts: tuple[Dept, ...] = ()


class DocumentAuditEntry(ApiModel):
    action: NonEmptyStr
    from_status: str | None = None
    to_status: str | None = None
    actor: NonEmptyStr
    reason: str | None = None
    occurred_at: datetime


class DocumentDetail(DocumentSummary):
    parse_quality: NonEmptyStr
    language: NonEmptyStr
    created_at: datetime
    audit: tuple[DocumentAuditEntry, ...] = ()  # most recent first, at most 20


class DocumentListResponse(ApiModel):
    items: tuple[DocumentSummary, ...]
    count: int = Field(ge=0)


class DocumentStatusAction(StrEnum):
    activate = "activate"  # draft -> active (family must have no other active version)
    archive = "archive"  # active -> archived, closing the effective window at effective_date
    withdraw = "withdraw"  # draft -> withdrawn (terminal)


class DocumentStatusRequest(ApiModel):
    """`effective_date` is the activation date for `activate` and the end of the window for `archive`;
    `withdraw` ignores it. `reason` is written to the audit row."""

    action: DocumentStatusAction
    effective_date: date | None = None
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def _date_matches_action(self) -> DocumentStatusRequest:
        if self.action in (DocumentStatusAction.activate, DocumentStatusAction.archive) and self.effective_date is None:
            raise ValueError(f"{self.action.value} requires effective_date")
        return self


class DocumentAclRequest(ApiModel):
    grant: tuple[Dept, ...] = ()
    revoke: tuple[Dept, ...] = ()
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def _non_empty_and_disjoint(self) -> DocumentAclRequest:
        if not self.grant and not self.revoke:
            raise ValueError("grant or revoke at least one department")
        if set(self.grant) & set(self.revoke):
            raise ValueError("a department cannot be granted and revoked in the same request")
        return self


class DocumentAclResponse(ApiModel):
    doc_id: NonEmptyStr
    document_key: NonEmptyStr
    granted: tuple[Dept, ...] = ()
    revoked: tuple[Dept, ...] = ()
    read_depts: tuple[Dept, ...] = ()


# ------------------------------------------------------------------------------- admin: policies (M3-03 / M4, DEC-012)


class PolicyKind(StrEnum):
    prompt = "prompt"
    rule = "rule"
    skill = "skill"
    retrieval_params = "retrieval_params"


class PolicyStatus(StrEnum):
    candidate = "candidate"
    approved = "approved"
    rejected = "rejected"
    released = "released"
    rolled_back = "rolled_back"


class PolicyResponse(ApiModel):
    policy_id: NonEmptyStr
    kind: PolicyKind
    name: NonEmptyStr
    version: NonEmptyStr
    status: PolicyStatus
    diff: dict[str, JsonValue]  # structured candidate diff (M4-03); never executable code
    evidence: dict[str, JsonValue]  # replay / gate report references; `gate.passed` must be true before a release
    created_by: NonEmptyStr
    created_at: datetime
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    released: bool = False  # the released pointer for (kind, name) currently points here


class PolicyListResponse(ApiModel):
    items: tuple[PolicyResponse, ...]
    count: int = Field(ge=0)


class PolicyDecision(StrEnum):
    approve = "approve"
    reject = "reject"


class PolicyDecisionRequest(ApiModel):
    """Four-eyes: the approver must not be the candidate's author."""

    decision: PolicyDecision
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class PolicyReleaseRequest(ApiModel):
    """Initial canary never above 10% (baseline 5.6 / M4-09)."""

    canary_percent: Annotated[int, Field(ge=0, le=10)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class PolicyRollbackRequest(ApiModel):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


# ------------------------------------------------------------------------------- admin: restricted payloads (M3-07, DEC-013)


class TracePayloadItem(ApiModel):
    node: NonEmptyStr
    kind: NonEmptyStr  # input | evidence_snapshot | model_output
    created_at: datetime
    expires_at: datetime
    kek_version: NonEmptyStr
    payload: JsonValue


class TracePayloadResponse(ApiModel):
    """Decrypted restricted payload of one trace; every read is logged with the caller's pseudonym and purpose."""

    trace_id: TraceId
    purpose: Annotated[str, Field(min_length=8, max_length=500)]
    items: tuple[TracePayloadItem, ...]
