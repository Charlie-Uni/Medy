"""Own one Agent lease, original allowance, durable journal and current-state recovery.

Terminal ownership is explicit through execute()/finish(); results need a confirmed commit.
No endpoint, automatic retry or new paid authorization is created.
Resources and profiles must be supplied by trusted server composition.
"""

from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from medops.application.agent_contracts import validate_run_snapshot
from medops.application.agent_final_gate import derived_profile
from medops.application.agent_loop import AgentLoop
from medops.application.agent_loop_ports import AgentLoopAbort, AgentLoopResult, LoopCheckpoint
from medops.application.agent_loop_state import LOOP_STATE_VERSION, LoopState
from medops.application.agent_planning import PlannerConfig
from medops.application.agent_review import PreparedReview
from medops.application.agent_runtime_state import (
    RUNTIME_STATE_VERSION,
    RuntimeBody,
    reconcile_budget,
    verify_accounting,
)
from medops.application.agent_terminal import AgentDelivery
from medops.bootstrap.agent_driver import AgentResources, Connection, PgAgentDriver, financial_cleanup
from medops.bootstrap.agent_observability import execution_attributes, execution_summary
from medops.bootstrap.agent_terminal import AgentTerminalOwner, read_delivery
from medops.core.deadline import DeadlineExceeded, deadline_scope
from medops.core.envelope import KeyProvider
from medops.core.errors import BusinessError
from medops.core.telemetry import annotate, run_metadata, span
from medops.domain.agent_execution import AgentBudget, AgentContext, PVAgentRun, StopReason
from medops.domain.identity import UserContext
from medops.infrastructure.db.agent_control import PgAgentControl
from medops.infrastructure.db.agent_facts import FactDatabaseBinding
from medops.infrastructure.db.agent_runtime import PgAgentRuntime
from medops.infrastructure.llm.accounting import call_scope
from medops.infrastructure.llm.budget_checkpoint import FrozenBudgetState, restore_consumed_budget
from medops.infrastructure.llm.execution_budget import ExecutionLimits, current_budget, execution_scope
from medops.infrastructure.llm.execution_journal import execution_journal_scope
from medops.infrastructure.llm.gateway import ModelGateway
from medops.infrastructure.llm.meter import MeteredGateway


class LeaseHeartbeat:
    def __init__(self, driver: PgAgentDriver, seconds: float):
        self.driver, self.seconds = driver, seconds
        self.stopped = threading.Event()
        self.failure_type: str | None = None
        self.thread = threading.Thread(target=self._run, name="agent-lease-renewal", daemon=True)

    def _run(self) -> None:
        while not self.stopped.wait(self.seconds / 3):
            try:
                with self.driver.connection() as conn:
                    self.driver._control(conn).renew(self.driver.lease, self.seconds)
            except Exception as exc:  # noqa: BLE001 - background boundary; retain type only
                self.failure_type = type(exc).__name__
                self.driver._stop_reason = exc.reason if isinstance(exc, AgentLoopAbort) else "dependency_error"
                return

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopped.set()
        self.thread.join(timeout=6)
        if self.thread.is_alive():
            self.driver._failed = True
            raise AgentLoopAbort("dependency_error")


class AgentExecution:
    def __init__(self, driver: PgAgentDriver, *, recovered: bool, lease_s: float, runtime: AgentRuntime):
        self.driver, self.recovered = driver, recovered
        self.runtime = runtime
        self.delivery: AgentDelivery | None = None
        self.heartbeat = LeaseHeartbeat(driver, lease_s)
        self.result: AgentLoopResult | None = None
        self.used = False

    def run(self) -> AgentLoopResult:
        with span("agent.loop"):
            if self.used:
                raise ValueError("agent_execution_already_used")
            self.used = True
            d = self.driver
            loop = AgentLoop(gateway=d.meter, config=d.head.body.config, driver=d, clock=d.clock)
            state = d.head.body.loop
            result = loop.resume(state) if self.recovered and state is not None else loop.run(d.head.body.run)
            self.result = result
            return result

    def review(self) -> PreparedReview:
        """Internal committed review, without publishing or extending this run."""
        return self.driver.prepare_review()

    def finish(self) -> AgentDelivery:
        """Only a confirmed, currently authorized committed terminal is returned."""
        if self.delivery is not None:
            with (
                run_metadata(
                    self.driver.context.identity.trace_id,
                    self.driver.context.versions.versions.model_dump(mode="json"),
                    kind="agent",
                ),
                span("agent.result", **{"medops.run_id": str(self.driver.context.identity.run_id)}),
            ):
                return self.runtime.result(self.driver.context, user=self.driver.context.principal)
        if not self.used or self.result is None:
            raise AgentLoopAbort("unsupported_requirement")
        d = self.driver
        with span("agent.terminal") as observed:
            try:
                self.delivery = AgentTerminalOwner(d).publish(self.result)
                annotate(observed, **execution_summary(d, self.delivery, None))
                return self.delivery
            except BaseException as exc:
                d._failed = True
                try:
                    with financial_cleanup(), d.connection() as conn:
                        d._store(conn).append(
                            d.lease,
                            "late_stop",
                            uuid4(),
                            {
                                "kind": "terminal_save_failed",
                                "reason": exc.reason if isinstance(exc, AgentLoopAbort) else "audit_failure",
                                "error_type": type(exc).__name__,
                            },
                            retained_until=d.head.retained_until,
                        )
                except Exception:  # noqa: BLE001 - best effort metadata only; original failure is re-raised
                    pass  # No committed result can be claimed while the audit store is unavailable.
                raise

    def execute(self) -> AgentDelivery:
        """Run the dynamic loop and its mandatory terminal owner, using one original allowance."""
        self.run()
        return self.finish()

    def _seal_stop(self, reason: StopReason) -> None:
        d = self.driver
        old = d.head.body.loop
        if old is not None and old.phase == "handoff":
            return
        state = LoopState(
            version=LOOP_STATE_VERSION,
            run=d.head.body.with_budget(FrozenBudgetState.model_validate(d.root.journal_state())).run,
            config=d.head.body.config,
            phase="handoff",
            captured_at=d.clock(),
            decision_id=None,
            history=old.history if old else (),
            stop_reason=reason,
            terminal_request=None,
            terminal_admitted_at=None,
            terminal_admission_budget=None,
        )
        d.checkpoint(LoopCheckpoint("handoff", state.run, reason=reason, state=state))

    def close(self, error: BaseException | None) -> None:
        d = self.driver
        try:
            self.heartbeat.stop()
            reason = (
                self.result.reason
                if self.result is not None
                else "cancelled"
                if isinstance(error, KeyboardInterrupt)
                else "dependency_error"
            )
            if not d._failed:
                try:
                    self._seal_stop(reason)
                except (DeadlineExceeded, BusinessError):
                    # The execution deadline/identity cannot authorize progress.
                    # Freeze below, then use accounting-only cleanup to release
                    # a still-owned lease. The immutable head deadline remains.
                    d._failed = True
                except AgentLoopAbort as exc:
                    if exc.reason not in {"timeout", "cancelled", "lease_lost"}:
                        raise
                    d._failed = True
        finally:
            # The root cannot admit a new request even if save/release or the
            # commit acknowledgement below fails. No zero-budget fallback.
            state = d.freeze_root()
        try:
            with financial_cleanup(), d.connection() as conn:
                store = d._store(conn)
                if store.control.get().terminal_ref is not None:
                    return
                store.control.fence(d.lease)
                if not d._failed:
                    head = store.save(d.lease, d.head.body.with_budget(state), state, expected_revision=d.head.revision)
                else:
                    head = d.head
                store.control.release(d.lease)
            d.head = head
        except BusinessError:
            pass  # revoked identity cannot save/release progress; financial events are already retained
        except AgentLoopAbort as exc:
            if exc.reason not in {"cancelled", "timeout", "lease_lost"}:
                raise


class AgentRuntime:
    def __init__(
        self,
        *,
        connection: Connection,
        gateway: ModelGateway,
        provider: KeyProvider,
        database_binding: FactDatabaseBinding,
        config: PlannerConfig,
        limits: ExecutionLimits,
        resources: Callable[[AgentContext, MeteredGateway], AgentResources],
        lease_s: float,
        retention_days: int,
    ):
        if (
            isinstance(lease_s, bool)
            or not math.isfinite(lease_s)
            or not 0 < lease_s <= 125
            or type(retention_days) is not int
            or retention_days <= 0
        ):
            raise ValueError("invalid_agent_runtime_configuration")
        self.connection, self.gateway, self.provider = connection, gateway, provider
        self.database_binding, self.config, self.limits = database_binding, config, limits
        self.resources, self.lease_s, self.retention_days = resources, lease_s, retention_days

    def _control(self, conn: Any, context: AgentContext) -> PgAgentControl:
        conn.execute("select set_config('medops.dept',%s,true)", (context.principal.dept.value,))
        return PgAgentControl(conn, context, database_binding=self.database_binding)

    def _profile(self, run: PVAgentRun) -> None:
        p = run.context.profile
        if (
            self.limits.token_limit > p.token_cap
            or self.limits.cost_limit_usd > p.cost_cap_microusd / 1e6
            or self.limits.timeout_s > p.timeout_ms / 1000
        ):
            raise AgentLoopAbort("budget_exceeded")

    def result(self, context: AgentContext, *, user: UserContext) -> AgentDelivery:
        if user != context.principal:
            raise AgentLoopAbort("safety_boundary")
        return read_delivery(self, context)

    def new_run(self, context: AgentContext) -> PVAgentRun:
        with self.connection() as conn:
            self._control(conn, context)._access()
            now = conn.execute("select clock_timestamp()").fetchone()[0]
        return PVAgentRun(
            context=context,
            status="running",
            decisions_consumed=0,
            budget=AgentBudget(
                accounted_tokens=0, reserved_tokens=0, accounted_cost_microusd=0, reserved_cost_microusd=0
            ),
            started_at=now,
            expires_at=now + timedelta(seconds=125),
            terminal=None,
        )

    @contextmanager
    def start(self, run: PVAgentRun) -> Iterator[AgentExecution]:
        run = validate_run_snapshot(run)
        self._profile(run)
        if current_budget() is not None:
            raise AgentLoopAbort("unsupported_recovery")
        remaining = (run.expires_at - datetime.now(UTC)).total_seconds()
        with deadline_scope(remaining), execution_scope(self.limits) as root:
            meter = MeteredGateway(self.gateway)
            resources = self.resources(run.context, meter)
            if (
                resources.final_config is not None
                and derived_profile(run.context, resources.final_config, meter.execution_prices) != run.context.profile
            ):
                raise AgentLoopAbort("version_conflict")
            with self.connection() as conn:
                control = self._control(conn, run.context)
                resources.check_bindings(conn, run.context)
                control.create(run)
                lease = control.claim(self.lease_s)
                anchor = time.monotonic()
                now = conn.execute("select clock_timestamp()").fetchone()[0]
                budget = FrozenBudgetState.model_validate(root.journal_state())
                end = min(
                    run.expires_at,
                    now + timedelta(seconds=max(0, budget.remaining_timeout_s - (time.monotonic() - anchor))),
                )
                body = RuntimeBody(
                    version=RUNTIME_STATE_VERSION, run=run, config=self.config, loop=None, frame=None, tool=None
                )
                head = PgAgentRuntime(control, self.provider).initialize(
                    lease, body, budget, budget_deadline=end, retained_until=now + timedelta(days=self.retention_days)
                )
            driver = PgAgentDriver(
                connection=self.connection,
                head=head,
                root=root,
                meter=meter,
                lease=lease,
                database_binding=self.database_binding,
                provider=self.provider,
                resources=resources,
            )
            with self._session(driver, recovered=False) as session:
                yield session

    @contextmanager
    def recover(self, context: AgentContext) -> Iterator[AgentExecution]:
        if current_budget() is not None:
            raise AgentLoopAbort("unsupported_recovery")
        with self.connection() as conn:
            control = self._control(conn, context)
            lease = control.claim(self.lease_s)
            store = PgAgentRuntime(control, self.provider)
            head = store.read(lock=True)
            if head.body.config != self.config or head.budget.snapshot.limits != self.limits:
                raise AgentLoopAbort("version_conflict")
            if (
                head.body.run.decisions_consumed != control.get().decisions_consumed
                or head.lease.generation >= lease.generation
            ):
                raise AgentLoopAbort("unsupported_recovery")
            self._profile(head.body.run)
            calls = store.calls()
            budget = reconcile_budget(head.budget, calls)
            verify_accounting(budget, calls, context)
            anchor = time.monotonic()
            now = conn.execute("select clock_timestamp()").fetchone()[0]
            remaining = min(budget.remaining_timeout_s, (head.budget_deadline - now).total_seconds())
            if remaining <= 0:
                raise AgentLoopAbort("timeout")
            budget = FrozenBudgetState.model_validate(
                budget.model_copy(
                    update={"checkpoint_id": uuid4(), "remaining_timeout_s": float(remaining)}
                ).model_dump(mode="json")
            )
            body = head.body.with_budget(budget)
            meter = MeteredGateway(self.gateway)
            resources = self.resources(context, meter)
            if (
                resources.final_config is not None
                and derived_profile(context, resources.final_config, meter.execution_prices) != context.profile
            ):
                raise AgentLoopAbort("version_conflict")
            resources.check_bindings(conn, context)
            head = store.save(lease, body, budget, expected_revision=head.revision)
        # COMMIT is confirmed; only now may a root/meter become usable.
        root = restore_consumed_budget(budget, expires_at_monotonic=anchor + remaining)
        meter.restore_calls(tuple(c.audit_entry for c in calls))
        driver = PgAgentDriver(
            connection=self.connection,
            head=head,
            root=root,
            meter=meter,
            lease=lease,
            database_binding=self.database_binding,
            provider=self.provider,
            resources=resources,
        )
        with execution_scope(self.limits, budget=root), self._session(driver, recovered=True) as session:
            yield session

    @contextmanager
    def _session(self, driver: PgAgentDriver, *, recovered: bool) -> Iterator[AgentExecution]:
        session = AgentExecution(driver, recovered=recovered, lease_s=self.lease_s, runtime=self)
        calls_at_start = driver.root.snapshot().calls
        with (
            run_metadata(
                driver.context.identity.trace_id, driver.context.versions.versions.model_dump(mode="json"), kind="agent"
            ),
            span("agent.execution", **execution_attributes(driver, recovered=recovered)) as observed,
        ):
            session.heartbeat.start()
            error: BaseException | None = None
            try:
                with (
                    execution_journal_scope(driver),
                    call_scope(
                        run_id=str(driver.context.identity.run_id),
                        attempt_id=str(driver.context.identity.attempt_id),
                        before_call=lambda: driver.check_access(driver.context, ()),
                    ),
                ):
                    yield session
            except BaseException as exc:
                error = exc
                raise
            finally:
                try:
                    session.close(error)
                except Exception as close_error:
                    if error is None:
                        error = close_error
                        raise
                finally:
                    annotate(
                        observed,
                        **execution_summary(
                            driver,
                            session.delivery,
                            error,
                            calls_at_start=calls_at_start,
                            handoff_reason=session.result.reason if session.result is not None else None,
                        ),
                    )
