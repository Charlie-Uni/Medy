"""Skill Registry (baseline 5.6, INV-AUTH-03, M2-11).

Execution order is fixed: lookup -> scopes (default deny, before anything that could leak schema details) ->
input schema -> version-set membership -> operation key -> handler under `run_node` (timeout; retries only for
idempotent skills) -> output contract -> safety layer 3. A refused output never reaches the caller: the payload
is replaced by a bare escalation. `execute_many` runs concurrently only skills marked `parallel_safe`; partial
results still pass the same per-output safety check (roadmap: parallel does not skip the final gate).
"""

from __future__ import annotations

import contextvars
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, NamedTuple

from pydantic import ValidationError

from medops.core.canonical import canonical_hash, operation_key
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError, MedOpsError
from medops.core.telemetry import annotate, run_metadata, span
from medops.domain.common import DocType, DomainModel, ReasonCode
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext, resolve_query_context
from medops.domain.safety import SafetyDecision, SafetyResult
from medops.domain.skill import SkillOutput, SkillSpec, SkillStatus
from medops.domain.state import VersionSet
from medops.harness.audit import ExecutionAudit, ExecutionAuditSnapshot
from medops.harness.contracts import MAX_RETRIES, NodeAttempt, NodeFailure, NodeSpec, run_node
from medops.harness.dependencies import HarnessDeps
from medops.harness.execution_record import execution_conditions
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.execution_budget import EXECUTION_BUDGET_VERSION, default_limits, execution_scope
from medops.infrastructure.llm.gateway import BudgetExceeded
from medops.infrastructure.llm.meter import MeteredGateway
from medops.safety.checks import SAFETY_VERSION, check_output_text

if TYPE_CHECKING:
    from medops.skills.agent_adapter import PVSkillAdapter

OPERATION_SCOPE = "skill"

EvidenceLookup = Callable[[UserContext, Sequence[str]], Sequence[Evidence]]
DocTypeLookup = Callable[[UserContext, Sequence[str]], Mapping[str, DocType]]


@dataclass(frozen=True)
class SkillContext:
    """What a Skill may use: the caller's identity, the run's versions and the shared services. No raw
    connections; the lookups run under the caller's identity in the fact plane."""

    user: UserContext
    versions: VersionSet
    deps: HarnessDeps
    evidence_lookup: EvidenceLookup
    doc_type_lookup: DocTypeLookup
    trace_id: str
    run_id: str
    as_of: date | None = None

    @property
    def query_context(self) -> QueryContext:
        context = self.deps.query_context or resolve_query_context(None, default_as_of=self.as_of or self.deps.as_of)
        if self.as_of is not None and self.as_of != context.as_of:
            raise BusinessError(ErrorCode.invalid_request, "skill and retrieval dates disagree")
        return context

    def pin_query_context(self) -> SkillContext:
        selected = self.query_context
        return replace(
            self, as_of=selected.as_of, deps=replace(self.deps, as_of=selected.as_of, query_context=selected)
        )


Handler = Callable[[SkillContext, Any], SkillOutput]


@dataclass(frozen=True)
class RegisteredSkill:
    spec: SkillSpec
    input_model: type[DomainModel]
    output_model: type[SkillOutput]
    handler: Handler


@dataclass(frozen=True)
class SkillRun:
    spec: SkillSpec
    output: SkillOutput
    attempts: tuple[NodeAttempt, ...]
    operation_key: str
    safety: SafetyResult
    audit: ExecutionAuditSnapshot | None = None


class SkillRequest(NamedTuple):
    name: str
    version: str
    input: Mapping[str, object]


class SkillRegistry:
    def __init__(
        self,
        *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], datetime] | None = None,
        max_parallel: int = 4,
    ) -> None:
        self._entries: dict[str, RegisteredSkill] = {}
        self._sleep = sleep
        self._clock = clock
        self._max_parallel = max(1, max_parallel)

    # ------------------------------------------------------------------ catalogue
    def register(self, entry: RegisteredSkill) -> None:
        tag = entry.spec.version_tag
        if tag in self._entries:
            raise ValueError(f"skill {tag} is already registered")
        if not issubclass(entry.output_model, SkillOutput) or not issubclass(entry.input_model, DomainModel):
            raise TypeError(f"skill {tag}: input must be a DomainModel and output a SkillOutput subclass")
        self._entries[tag] = entry

    def get(self, name: str, version: str) -> RegisteredSkill:
        entry = self._entries.get(f"{name}@{version}")
        if entry is None:
            raise BusinessError(ErrorCode.not_found, f"unknown skill {name}@{version}")
        return entry

    def entries(self) -> tuple[RegisteredSkill, ...]:
        return tuple(self._entries[k] for k in sorted(self._entries))

    def catalog(self) -> tuple[SkillSpec, ...]:
        return tuple(e.spec for e in self.entries())

    def version_set(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def describe(self, name: str, version: str) -> dict[str, Any]:
        entry = self.get(name, version)
        return {
            "spec": entry.spec.model_dump(mode="json"),
            "input_schema": entry.input_model.model_json_schema(),
            "output_schema": entry.output_model.model_json_schema(),
        }

    def agent_adapter(self) -> PVSkillAdapter:
        """Expose the PV adapter through the Registry's existing public package boundary."""
        from medops.skills.agent_adapter import PVSkillAdapter

        return PVSkillAdapter(self)

    # ------------------------------------------------------------------ execution
    def execute(self, name: str, version: str, raw_input: Mapping[str, object], *, context: SkillContext) -> SkillRun:
        context = context.pin_query_context()
        journal = context.deps.audit or ExecutionAudit()
        journal.bind(context.trace_id, context.user.user_id)
        context = replace(context, deps=replace(context.deps, audit=journal))
        limits = context.deps.execution_limits or default_limits(timeout_s=self.get(name, version).spec.timeout_s)
        limits = limits.model_copy(update={"timeout_s": min(limits.timeout_s, self.get(name, version).spec.timeout_s)})
        if not isinstance(context.deps.gateway, MeteredGateway):
            context = replace(context, deps=replace(context.deps, gateway=MeteredGateway(context.deps.gateway)))
        meter = context.deps.gateway
        assert isinstance(meter, MeteredGateway)
        entry = self.get(name, version)
        with (
            run_metadata(context.trace_id, context.versions.model_dump(mode="json"), kind="skill"),
            call_scope(run_id=context.run_id),
            execution_scope(limits) as budget,
            span("skill.run", skill=f"{name}@{version}") as current,
        ):
            journal.record_event(
                "skill_execution_input",
                {
                    "input": {
                        "skill": f"{name}@{version}",
                        "input": raw_input,
                        "user": context.user.model_dump(mode="json"),
                        "versions": context.versions.model_dump(mode="json"),
                        "query_context": context.query_context.model_dump(mode="json")
                        if context.query_context
                        else None,
                    },
                    "conditions": execution_conditions(context.deps, limits, shared_limits=budget.limits),
                    "skill_spec": entry.spec.model_dump(mode="json"),
                    "input_schema_sha256": canonical_hash(entry.input_model.model_json_schema()),
                    "output_schema_sha256": canonical_hash(entry.output_model.model_json_schema()),
                },
            )
            result = self._execute(name, version, raw_input, context=context)
            snapshot = budget.snapshot()
            annotate(
                current,
                outcome=result.output.status.value,
                execution_budget_version=EXECUTION_BUDGET_VERSION,
                execution_timeout_s=snapshot.limits.timeout_s,
                execution_token_limit=snapshot.limits.token_limit,
                execution_cost_limit_usd=snapshot.limits.cost_limit_usd,
                execution_accounted_tokens=snapshot.accounted_tokens,
                execution_accounted_cost_usd=snapshot.accounted_cost_usd,
                execution_reserved_tokens=snapshot.reserved_tokens,
                execution_budget_blocked=snapshot.blocked_reason,
            )
            journal.ensure_complete()
            meter.call_journal.ensure_complete()
            return replace(result, audit=journal.snapshot())

    def _execute(self, name: str, version: str, raw_input: Mapping[str, object], *, context: SkillContext) -> SkillRun:
        entry = self.get(name, version)
        spec = entry.spec
        required = spec.resolve_scopes(context.user)
        if not context.user.has_scopes(required):
            missing = sorted(set(required) - set(context.user.acl_scopes))
            raise BusinessError(
                ErrorCode.forbidden,
                f"skill {spec.version_tag} requires scopes the caller does not hold",
                detail=f"missing={missing}",
            )
        if not isinstance(raw_input, Mapping):
            raise BusinessError(ErrorCode.schema_violation, f"skill {spec.version_tag} input must be a JSON object")
        try:
            payload = entry.input_model.model_validate(dict(raw_input))
        except ValidationError as exc:
            raise BusinessError(
                ErrorCode.schema_violation,
                f"skill {spec.version_tag} input rejected by its schema ({exc.error_count()} error(s))",
                detail=str(exc)[:500],
            ) from None
        if spec.version_tag not in context.versions.skill_version_set:
            raise InfrastructureError(
                ErrorCode.internal_error,
                detail=f"run version set does not record {spec.version_tag} (INV-HAR-05)",
                retryable=False,
            )
        key = operation_key(
            OPERATION_SCOPE,
            context.run_id,
            spec.version_tag,
            {
                "input": payload.model_dump(mode="json"),
                "user": context.user.model_dump(mode="json"),
                "versions": context.versions.model_dump(mode="json"),
                "query_context": context.query_context.model_dump(mode="json"),
            },
        )
        node = NodeSpec(
            name=f"skill:{spec.name}",
            timeout_s=spec.timeout_s,
            max_retries=MAX_RETRIES if spec.idempotent else 0,
        )
        try:
            output, attempts = run_node(
                node, key, lambda: entry.handler(context, payload), sleep=self._sleep, clock=self._clock
            )
        except NodeFailure as failure:
            assert context.deps.audit is not None
            context.deps.audit.record_attempts(failure.attempts)
            if isinstance(failure.error, BusinessError):
                raise failure.error from None
            output = SkillOutput(
                status=SkillStatus.escalated,
                reason_codes=(
                    ReasonCode.budget_exceeded
                    if isinstance(failure.error, BudgetExceeded)
                    else ReasonCode.system_failure,
                ),
                detail=f"{type(failure.error).__name__}: {str(failure.error)[:160]}",
            )
            return SkillRun(
                spec=spec,
                output=output,
                attempts=tuple(failure.attempts),
                operation_key=key,
                safety=SafetyResult(decision=SafetyDecision.allow, checker_version=SAFETY_VERSION),
            )
        assert context.deps.audit is not None
        context.deps.audit.record_attempts(attempts)
        if not isinstance(output, entry.output_model):
            raise InfrastructureError(
                ErrorCode.internal_error,
                detail=f"skill {spec.version_tag} returned {type(output).__name__}, not {entry.output_model.__name__}",
                retryable=False,
            )
        safety = check_output_text(output.rendered_texts(), off_label=spec.name == "off_label_check")
        if safety.decision is not SafetyDecision.allow:
            output = SkillOutput(status=SkillStatus.escalated, reason_codes=safety.reason_codes, detail=safety.detail)
        return SkillRun(spec=spec, output=output, attempts=tuple(attempts), operation_key=key, safety=safety)

    def execute_many(
        self, requests: Sequence[SkillRequest], *, context: SkillContext
    ) -> tuple[SkillRun | MedOpsError, ...]:
        context = context.pin_query_context()  # every child shares the same day even when a batch crosses midnight
        limits = context.deps.execution_limits or default_limits(
            timeout_s=sum(self.get(r.name, r.version).spec.timeout_s for r in requests) or 1
        )
        with execution_scope(limits):
            return self._execute_many(requests, context=context)

    def _execute_many(
        self, requests: Sequence[SkillRequest], *, context: SkillContext
    ) -> tuple[SkillRun | MedOpsError, ...]:
        """Concurrent only for `parallel_safe` skills; the rest run one after another in request order."""
        results: list[SkillRun | MedOpsError | None] = [None] * len(requests)
        parallel = [i for i, r in enumerate(requests) if self.get(r.name, r.version).spec.parallel_safe]
        if parallel:
            with ThreadPoolExecutor(max_workers=min(self._max_parallel, len(parallel))) as pool:
                futures = {
                    i: pool.submit(contextvars.copy_context().run, self._guarded, requests[i], context)
                    for i in parallel
                }
                for i, future in futures.items():
                    results[i] = future.result()
        for i, request in enumerate(requests):
            if results[i] is None:
                results[i] = self._guarded(request, context)
        return tuple(r for r in results if r is not None)

    def _guarded(self, request: SkillRequest, context: SkillContext) -> SkillRun | MedOpsError:
        try:
            context = replace(context, deps=replace(context.deps, audit=None))  # sibling audit isolation
            return self.execute(request.name, request.version, request.input, context=context)
        except MedOpsError as exc:
            return exc
