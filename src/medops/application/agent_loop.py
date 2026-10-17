"""Model-selected sequential PV actions. Internal composition only; no terminal publisher.

A mandatory trusted driver owns transaction commits/checkpoints. This slice does
not implement durable recovery, final business validation or public endpoints.
"""

from __future__ import annotations

import logging
import traceback
from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from medops.application.agent_contracts import AgentContractError, admit_action, validate_run_snapshot
from medops.application.agent_loop_ports import AgentLoopAbort, AgentLoopDriver, AgentLoopResult, LoopCheckpoint
from medops.application.agent_loop_state import (
    FATAL_OUTCOMES,
    LOOP_STATE_VERSION,
    CommittedDecision,
    LoopState,
    encode_loop_state,
)
from medops.application.agent_loop_validation import validate_tool_commit
from medops.application.agent_planning import PlannerConfig, PlanningBoard, planning_prompt_sha256
from medops.application.agent_progress import AgentProgress
from medops.application.agent_tool_results import AgentToolOutcome
from medops.application.agent_tools import tool_contract_sha256
from medops.core.deadline import CURRENT_DEADLINE, DeadlineExceeded, check_deadline, deadline_scope, execution_admission
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.core.money import usd_to_microusd
from medops.core.telemetry import run_metadata
from medops.domain.agent_actions import ClarifyAction, EscalateAction, FinishAction
from medops.domain.agent_execution import AgentBudget, BoundAction, EvidenceHandle, PVAgentRun, StopReason, utc_time
from medops.domain.safety import SafetyDecision
from medops.infrastructure.llm.accounting import call_scope, check_call_ownership, new_call
from medops.infrastructure.llm.execution_budget import (
    BudgetProtection,
    ExecutionBudget,
    allowance,
    check_execution_budget,
    current_budget,
)
from medops.infrastructure.llm.gateway import BudgetExceeded, ModelOutputInvalid, ModelResponse
from medops.infrastructure.llm.meter import MeteredGateway
from medops.safety.checks import check_input

log = logging.getLogger(__name__)


def _failure_location(exc: Exception) -> None:
    frames = traceback.extract_tb(exc.__traceback__)[-3:]
    log.warning(
        "agent_loop_failure type=%s location=%s",
        type(exc).__name__,
        [(frame.filename, frame.lineno, frame.name) for frame in frames],
    )


class AgentLoop:
    def __init__(
        self,
        *,
        gateway: MeteredGateway,
        config: PlannerConfig,
        driver: AgentLoopDriver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        if not isinstance(gateway, MeteredGateway):
            raise ValueError("agent_requires_metered_gateway")
        self.gateway, self.driver, self.clock = gateway, driver, clock
        self.config = PlannerConfig.model_validate(config.model_dump(mode="python", warnings=False))
        gateway.execution_prices.require(self.config.model_id)  # no inferred price/default model
        self._used = False

    def run(self, initial: PVAgentRun) -> AgentLoopResult:
        if self._used:
            raise ValueError("agent_loop_already_used")
        self._used = True
        self._budget: ExecutionBudget | None = None
        self._run = initial = validate_run_snapshot(initial)
        if initial.status != "running":
            raise AgentContractError("agent_not_running")
        self._registry: tuple[EvidenceHandle, ...] = ()
        self._outcomes: tuple[AgentToolOutcome, ...] = ()
        self._board = PlanningBoard()
        self._progress = AgentProgress()
        self._history: tuple[CommittedDecision, ...] = ()
        self._admitted_at: datetime | None = None
        if (
            initial.decisions_consumed
            or any(initial.budget.model_dump().values())
            or initial.context.versions.planning_prompt_sha256 != planning_prompt_sha256()
        ):
            return self._handoff("unsupported_recovery")
        if initial.context.versions.tool_contract_sha256 != tool_contract_sha256():
            return self._handoff("version_conflict")
        budget = current_budget()
        if budget is None or CURRENT_DEADLINE.get() is None:
            return self._handoff("budget_exceeded")
        profile = initial.context.profile
        limits = budget.limits
        if (
            limits.token_limit > profile.token_cap
            or usd_to_microusd(limits.cost_limit_usd) > profile.cost_cap_microusd
            or limits.timeout_s > profile.timeout_ms / 1000
        ):
            return self._handoff("budget_exceeded")
        # A fresh run cannot silently attach to another run's spent or pending allowance.
        snapshot = budget.snapshot()
        if (
            snapshot.accounted_tokens
            or snapshot.reserved_tokens
            or snapshot.accounted_cost_usd
            or snapshot.reserved_cost_usd
            or snapshot.calls
            or snapshot.protected_tokens
            or snapshot.protected_cost_usd
        ):
            return self._handoff("unsupported_recovery")
        self._budget = budget  # bind only after all fresh-run/zero-parent checks pass
        try:
            self._guard()
            context = self._run.context
            texts = [context.narrative, *(r.description for r in context.requirements)]
            if context.source_scope.requested_document:
                texts.append(context.source_scope.requested_document)
            if any(check_input(text).decision is not SafetyDecision.allow for text in texts):
                return self._handoff("safety_boundary")
            budget.protect_remaining(
                BudgetProtection(
                    tokens=profile.final_reserve_tokens,
                    cost_usd=profile.final_reserve_cost_microusd / 1_000_000,
                )
            )
            remaining = (initial.expires_at - self._now()).total_seconds()
            with (
                deadline_scope(remaining),
                execution_admission(),
                run_metadata(
                    context.identity.trace_id, context.versions.versions.model_dump(mode="json"), kind="agent"
                ),
            ):
                return self._loop()
        except AgentLoopAbort as exc:
            return self._handoff(exc.reason)
        except (DeadlineExceeded, TimeoutError):
            return self._handoff("timeout")
        except BudgetExceeded:
            return self._handoff("budget_exceeded")
        except BusinessError:
            return self._handoff("safety_boundary")
        except InfrastructureError as exc:
            reason: StopReason = (
                "timeout"
                if exc.code is ErrorCode.dependency_timeout
                else ("audit_failure" if exc.code is ErrorCode.audit_unavailable else "dependency_error")
            )
            return self._handoff(reason)
        except Exception as exc:  # noqa: BLE001 - fixed stop code, log type/location only
            _failure_location(exc)
            return self._handoff("dependency_error")

    def _now(self) -> datetime:
        return utc_time(self.clock())

    def _snapshot(self) -> PVAgentRun:
        if self._budget is not None:
            s = self._budget.snapshot()
            self._run = self._run.model_copy(
                update={
                    "budget": AgentBudget(
                        accounted_tokens=s.accounted_tokens,
                        reserved_tokens=s.reserved_tokens,
                        accounted_cost_microusd=usd_to_microusd(s.accounted_cost_usd),
                        reserved_cost_microusd=usd_to_microusd(s.reserved_cost_usd),
                    )
                }
            )
        return validate_run_snapshot(self._run)

    def _local_guard(self) -> None:
        if self._budget is None or current_budget() is not self._budget:
            raise AgentLoopAbort("unsupported_recovery")
        check_deadline()
        check_execution_budget()
        now = self._now()
        if not self._run.started_at <= now < self._run.expires_at:
            raise DeadlineExceeded()
        self.driver.check_access(self._run.context, self._registry)
        check_deadline()

    def _guard(self) -> None:
        check_call_ownership()  # inherited parent guard, not recursive from before_call
        self._local_guard()

    def _record(self, event: LoopCheckpoint) -> None:
        try:
            # A refused old run/foreign allowance has no bound progress here.
            # None instructs storage to preserve its existing state, never reset it.
            progress = self._progress.snapshot() if self._budget is not None else None
            protection = self._budget.protection() if self._budget is not None else None
            state = (
                LoopState(
                    version=LOOP_STATE_VERSION,
                    run=event.run,
                    config=self.config,
                    phase=event.phase,
                    captured_at=self._now(),
                    decision_id=event.decision_id,
                    history=self._history,
                    stop_reason=cast(StopReason, event.reason) if event.phase == "handoff" else None,
                    terminal_request=event.action if event.phase == "handoff" else None,
                    terminal_admitted_at=self._admitted_at if event.phase == "handoff" and event.action else None,
                )
                if self._budget is not None
                else None
            )
            if state is not None:
                encode_loop_state(state)  # validate complete, bounded restricted image before the driver sees it
            self.driver.checkpoint(replace(event, progress=progress, budget_protection=protection, state=state))
        except Exception as exc:  # noqa: BLE001 - driver storage failures must stop, with a fixed code
            _failure_location(exc)
            raise AgentLoopAbort("audit_failure") from None

    def _loop(self) -> AgentLoopResult:
        while self._run.decisions_consumed < self._run.context.profile.max_decision_steps:
            self._guard()
            prior_count = self._run.decisions_consumed
            self._run = self._snapshot().model_copy(update={"decisions_consumed": prior_count + 1})
            decision_id = uuid4()
            context = self._run.context
            with call_scope(
                run_id=str(context.identity.run_id),
                attempt_id=f"{context.identity.attempt_id}/decision:{decision_id}",
                before_call=self._local_guard,
            ):
                request = self._board.request(self._run, self.config)
                request = request.model_copy(update={"call": new_call(request, self.gateway.provider)})
                self._record(LoopCheckpoint("decision_started", self._run, decision_id, request=request))
                item = allowance(request, self.gateway.execution_prices)
                budget = current_budget()
                if budget is None:
                    raise AgentLoopAbort("budget_exceeded")
                s = budget.snapshot()
                p = context.profile
                if (
                    s.accounted_tokens + s.reserved_tokens + item.tokens + p.final_reserve_tokens > s.limits.token_limit
                    or usd_to_microusd(s.accounted_cost_usd + s.reserved_cost_usd + item.cost_usd)
                    + p.final_reserve_cost_microusd
                    > usd_to_microusd(s.limits.cost_limit_usd)
                ):
                    return self._handoff("budget_exceeded")
                before = {r.call.call_id for r in self.gateway.receipts}
                response: ModelResponse | None = None
                invalid = False
                try:
                    response = self.gateway.complete(request)  # one logical planning request; no repair/retry loop
                    invalid = response.truncated
                except ModelOutputInvalid as exc:
                    response, invalid = exc.model_response, True
                finally:
                    self.gateway.call_journal.ensure_complete()
                    receipts = tuple(r.call.call_id for r in self.gateway.receipts if r.call.call_id not in before)
                    self._record(
                        LoopCheckpoint(
                            "planning_returned", self._snapshot(), decision_id, response=response, receipt_ids=receipts
                        )
                    )
            self._guard()
            admission_run = self._snapshot().model_copy(update={"decisions_consumed": prior_count})
            admitted_at = self._now()
            self._admitted_at = admitted_at
            try:
                if invalid or response is None:
                    raise AgentContractError("invalid_agent_payload")
                action = admit_action(
                    response.text,
                    run=admission_run,
                    action_id=decision_id,
                    evidence_registry=self._registry,
                    now=admitted_at,
                )
            except AgentContractError as exc:
                if exc.code in {"agent_budget_exhausted", "agent_final_reserve"}:
                    return self._handoff("budget_exceeded")
                self._board.observe(None, None)
                self._progress.reset()
                self._history += (
                    CommittedDecision(
                        decision_id=decision_id,
                        decision_index=prior_count + 1,
                        admitted_at=admitted_at,
                        observed_at=self._now(),
                        admission_budget=admission_run.budget,
                        action=None,
                        outcome=None,
                        rejected=exc.code,
                    ),
                )
                self._record(LoopCheckpoint("proposal_rejected", self._run, decision_id, reason=exc.code))
                continue  # a NEW counted decision, never a free format-repair request
            proposal = action.proposal
            if isinstance(proposal, (FinishAction, ClarifyAction, EscalateAction)):
                reason: StopReason = (
                    "completed"
                    if isinstance(proposal, FinishAction)
                    else ("clarification_required" if isinstance(proposal, ClarifyAction) else proposal.reason)
                )
                return self._handoff(reason, action)
            before = {r.call.call_id for r in self.gateway.receipts}
            outcome = self.driver.execute_tool(action, admission_run=admission_run, evidence_registry=self._registry)
            self._guard()
            observed_at = self._now()
            try:
                outcome, registry = validate_tool_commit(action, outcome, self._run, self._registry, now=observed_at)
            except AgentLoopAbort:
                raise
            except (ValueError, TypeError, AttributeError):
                raise AgentLoopAbort("audit_failure") from None
            actual = {r.call.call_id for r in self.gateway.receipts if r.call.call_id not in before}
            if set(outcome.call_receipt_ids) != actual:
                raise AgentLoopAbort("audit_failure")
            for receipt in self.gateway.receipts:
                if receipt.call.call_id in actual and (
                    receipt.call.run_id != str(context.identity.run_id)
                    or f"action:{action.action_id}" not in (receipt.call.attempt_id or "")
                ):
                    raise AgentLoopAbort("audit_failure")
            self._snapshot()
            try:
                # Stage both projections. A size/shape failure must not leave
                # progress ahead of the last reconstructible observation.
                next_board, next_progress = deepcopy(self._board), deepcopy(self._progress)
                progress = next_progress.observe(action, outcome, registry)
                next_board.observe(action, outcome)
            except (ValueError, TypeError, AttributeError):
                raise AgentLoopAbort("audit_failure") from None
            # A complete checkpoint must include the same committed observation
            # the next planner sees. Persistence failure still stops this loop.
            self._board, self._progress = next_board, next_progress
            self._registry = registry
            self._outcomes += (outcome,)
            self._history += (
                CommittedDecision(
                    decision_id=decision_id,
                    decision_index=prior_count + 1,
                    admitted_at=admitted_at,
                    observed_at=observed_at,
                    admission_budget=admission_run.budget,
                    action=action,
                    outcome=outcome,
                    rejected=None,
                ),
            )
            self._record(
                LoopCheckpoint(
                    "tool_committed",
                    self._run,
                    decision_id,
                    action=action,
                    outcome=outcome,
                    receipt_ids=outcome.call_receipt_ids,
                )
            )
            if outcome.kind in FATAL_OUTCOMES:
                return self._handoff(FATAL_OUTCOMES[outcome.kind])
            if progress.consecutive >= context.profile.same_no_progress_limit:
                return self._handoff("no_progress")
        return self._handoff("step_limit")

    def _handoff(self, reason: StopReason, action: BoundAction | None = None) -> AgentLoopResult:
        self._snapshot()
        failed = False
        try:
            self._record(LoopCheckpoint("handoff", self._run, action=action, reason=reason))
        except AgentLoopAbort:
            failed, reason, action = True, "audit_failure", None
        return AgentLoopResult(self._run, reason, action, self._registry, self._outcomes, failed)
