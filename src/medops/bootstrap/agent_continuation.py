"""Trusted clarification service. Explicit commands, same case, genuinely new runs.

No HTTP auto-start, production grant default, hosted experiment or background retry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from psycopg.errors import UniqueViolation

from medops.application.agent_continuation import (
    ClarificationCase,
    ClarificationExecution,
    ClarificationPolicy,
    ContinuationAuthorization,
    ContinueAgent,
    ContinuedAgent,
    clarified_context,
)
from medops.application.agent_final_gate import FinalGateConfig
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_planning import PlannerConfig
from medops.application.agent_terminal import AgentDelivery
from medops.bootstrap.agent_execution import AgentRuntime
from medops.bootstrap.agent_services import bind_new_agent_context, production_agent_runtime
from medops.core.canonical import canonical_hash
from medops.core.deadline import deadline_scope
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.agent_execution import AgentContext
from medops.domain.common import Sha256
from medops.domain.identity import UserContext
from medops.domain.safety import SafetyDecision
from medops.infrastructure.db.agent_clarification import PgAgentClarification, owned_context, terminal_accounting
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts
from medops.infrastructure.db.final_output import acquire_output_fence, require_same_user
from medops.safety.checks import check_input

if TYPE_CHECKING:
    from medops.bootstrap.runtime import ProductionRuntime


class AgentContinuationService:
    def __init__(
        self,
        runtime: ProductionRuntime,
        *,
        database_binding: FactDatabaseBinding,
        source_runtime: Callable[[AgentContext], AgentRuntime],
        prepare: Callable[[AgentContext], tuple[AgentContext, AgentRuntime]],
    ):
        self.runtime, self.database_binding = runtime, database_binding
        self.source_runtime, self.prepare = source_runtime, prepare
        if runtime._key_provider is None:
            raise AgentLoopAbort("audit_failure")

    def _user(self, conn: Any, authorization: str, expected: UserContext | None = None) -> UserContext:
        acquire_output_fence(conn)
        user = self.runtime.authenticator.authenticate(authorization, self.runtime.directory(conn))
        if expected is not None:
            require_same_user(expected, user)
        self.runtime.bind_identity(conn, user)
        return user

    def _context(self, conn: Any, user: UserContext, run_id: UUID) -> AgentContext:
        assert self.runtime._key_provider is not None
        return owned_context(
            conn, user, run_id, provider=self.runtime._key_provider, database_binding=self.database_binding
        )

    def authorize(self, grant: ContinuationAuthorization, *, authorization: str) -> None:
        """Record an already approved, scoped batch; the object itself grants no paid permission."""
        grant = ContinuationAuthorization.model_validate(grant.model_dump(mode="json"))
        with deadline_scope(5.0), self.runtime.connection() as conn:
            PgAgentClarification(conn, self._user(conn, authorization)).batch(grant)

    def open_case(self, source_run_id: UUID, policy: ClarificationPolicy, *, authorization: str) -> ClarificationCase:
        policy = ClarificationPolicy.model_validate(policy.model_dump(mode="json"))
        with deadline_scope(5.0), self.runtime.connection() as conn:
            user = self._user(conn, authorization)
            context = self._context(conn, user, source_run_id)
        source = self.source_runtime(context).result(context, user=user)
        if source.run.status != "awaiting_clarification" or source.run.budget.reserved_cost_microusd:
            raise AgentLoopAbort("unsupported_requirement")
        with deadline_scope(5.0), self.runtime.connection() as conn:
            self._user(conn, authorization, user)
            cost, known = terminal_accounting(conn, source)
            return PgAgentClarification(conn, user).open_case(context, policy, source_cost=cost, known_cost=known)

    def case(self, case_id: UUID, *, authorization: str) -> ClarificationCase:
        with deadline_scope(5.0), self.runtime.connection() as conn:
            return PgAgentClarification(conn, self._user(conn, authorization)).read(case_id)

    def delete(self, case_id: UUID, *, expected_revision: int, authorization: str) -> ClarificationCase:
        with deadline_scope(5.0), self.runtime.connection() as conn:
            return PgAgentClarification(conn, self._user(conn, authorization)).delete(
                case_id, expected_revision=expected_revision
            )

    def executions(
        self, case_id: UUID, *, authorization: str, after_ordinal: int = -1, limit: int = 32
    ) -> tuple[ClarificationExecution, ...]:
        with deadline_scope(5.0), self.runtime.connection() as conn:
            return PgAgentClarification(conn, self._user(conn, authorization)).executions(
                case_id, after_ordinal=after_ordinal, limit=limit
            )

    def continue_case(self, source_run_id: UUID, command: ContinueAgent, *, authorization: str) -> ContinuedAgent:
        try:
            return self._continue(source_run_id, command, authorization=authorization)
        except (BusinessError, AgentLoopAbort, InfrastructureError):
            raise
        except UniqueViolation:
            raise AgentLoopAbort("version_conflict") from None
        except Exception as exc:  # noqa: BLE001 - do not expose encrypted input or DB/provider exception messages
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__, retryable=False) from None

    def _continue(self, source_run_id: UUID, command: ContinueAgent, *, authorization: str) -> ContinuedAgent:
        command = ContinueAgent.model_validate(command.model_dump(mode="json"))
        digest = canonical_hash({"source_run_id": str(source_run_id), "command": command.model_dump(mode="json")})
        with deadline_scope(5.0), self.runtime.connection() as conn:
            user = self._user(conn, authorization)
            existing = PgAgentClarification(conn, user).command(command.command_id)
            if existing:
                if existing[2] != digest:
                    raise AgentLoopAbort("version_conflict")
                if not existing[4]:
                    # May have reached a provider before a lost acknowledgement.
                    # Never recover automatically or reserve a replacement run.
                    raise AgentLoopAbort("unsupported_recovery")
                context = self._context(conn, user, existing[0])
                if canonical_hash(context.model_dump(mode="json")) != existing[3]:
                    raise AgentLoopAbort("audit_failure")
            else:
                context = self._context(conn, user, source_run_id)
                store = PgAgentClarification(conn, user)
                row = store._case(context.identity.case_id)
                store._live(row)
                if row[2] != command.expected_revision or row[1] != source_run_id:
                    raise AgentLoopAbort("version_conflict")
        if existing:
            return self._result(context, authorization=authorization, user=user)
        source = self.source_runtime(context).result(context, user=user)
        if source.run.budget.reserved_cost_microusd:
            raise AgentLoopAbort("unsupported_recovery")
        try:
            proposal = clarified_context(source, command)
        except ValueError:
            raise BusinessError(ErrorCode.invalid_request, "invalid or oversized clarification") from None
        if any(check_input(a.value).decision is not SafetyDecision.allow for a in command.answers):
            raise AgentLoopAbort("safety_boundary")
        context, executor = self.prepare(proposal)
        # Preparation can refresh versions/profile and resolve current sources;
        # it cannot rewrite the user's actual input or extend task identity.
        if (
            context.identity != proposal.identity
            or context.principal != user
            or context.narrative != proposal.narrative
            or context.requirements != proposal.requirements
            or context.query_context != proposal.query_context
            or context.synthetic is not True
            or context.source_type != proposal.source_type
            or context.clarifiable_fields != proposal.clarifiable_fields
            or context.source_scope.requested_document != proposal.source_scope.requested_document
            or context.source_scope.requested_version != proposal.source_scope.requested_version
        ):
            raise AgentLoopAbort("safety_boundary")
        with deadline_scope(5.0), self.runtime.connection() as conn:
            self._user(conn, authorization, user)
            PgAgentClarification(conn, user).reserve(
                context,
                command_id=command.command_id,
                batch_id=command.batch_id,
                source_run_id=source_run_id,
                request_sha256=digest,
                expected_revision=command.expected_revision,
            )
        selected_resources = executor.resources

        def resources(ctx, meter):
            selected = selected_resources(ctx, meter)

            def check(conn, current):
                self._user(conn, authorization, user)
                PgAgentClarification(conn, user).guard(current, request_sha256=digest)
                selected.check_bindings(conn, current)

            return replace(selected, check_bindings=check)

        executor.resources = resources
        # Reservation and revised case commit BEFORE any provider admission.
        # Any uncertain failure retains the full allocation and occupied command.
        delivery: AgentDelivery | None = None
        try:
            run = executor.new_run(context)
            with executor.start(run) as execution:
                driver = execution.driver
                with driver.connection() as conn:
                    driver._store(conn).append(
                        driver.lease,
                        "checkpoint",
                        command.command_id,
                        {
                            "kind": "clarification_continuation",
                            "source_run_id": str(source_run_id),
                            "case_id": str(context.identity.case_id),
                            "command_id": str(command.command_id),
                            "batch_id": str(command.batch_id),
                            "request_sha256": digest,
                        },
                        retained_until=driver.head.retained_until,
                    )
                delivery = execution.execute()
        finally:
            executor.resources = selected_resources
            if delivery is not None and not delivery.run.budget.reserved_cost_microusd:
                # A confirmed terminal with complete accounting may release the
                # unused allowance, even if the user was revoked/deleted meanwhile.
                with self.runtime.connection() as conn:
                    PgAgentClarification(conn, user).settle(context, delivery=delivery)
        return self._result(context, authorization=authorization, user=user)

    def _result(self, context: AgentContext, *, authorization: str, user: UserContext) -> ContinuedAgent:
        # The case lock/fact fence spans the result read and return-commit. A
        # concurrent deletion cannot publish a previously authorized body later.
        with deadline_scope(5.0), self.runtime.connection() as conn:
            self._user(conn, authorization, user)
            store = PgAgentClarification(conn, user)
            row = store._case(context.identity.case_id, lock=True)
            store._live(row)
            if row[1] != context.identity.run_id:
                raise AgentLoopAbort("version_conflict")
            delivery = self.source_runtime(context).result(context, user=user)
            return ContinuedAgent(case=store.read(context.identity.case_id), delivery=delivery)


def production_agent_continuation(
    runtime: ProductionRuntime,
    *,
    config: PlannerConfig,
    final_config: FinalGateConfig,
    database_binding: FactDatabaseBinding,
    rubric_sha256: Sha256,
    lease_s: float,
) -> AgentContinuationService:
    """Explicit server composition; no new public paid admission endpoint."""

    def executor(context):
        return production_agent_runtime(
            runtime,
            context,
            config=config,
            final_config=final_config,
            database_binding=database_binding,
            lease_s=lease_s,
        )

    def prepare(proposal):
        context = proposal.model_copy(
            update={
                "versions": proposal.versions.model_copy(
                    update={"fact_database_id": database_binding.fact_database_id, "rubric_sha256": rubric_sha256}
                )
            }
        )
        with runtime.connection() as conn:
            runtime.bind_identity(conn, context.principal)
            facts = PgAgentFacts(conn, context.principal, database_binding=database_binding)
            selector = context.source_scope
            if selector.requested_document is not None:
                scope = facts.resolve_scope(
                    selector.requested_document, selector.requested_version, query_context=context.query_context
                )
                if scope.resolution == "denied_or_unavailable":
                    raise AgentLoopAbort("safety_boundary")
                context = context.model_copy(update={"source_scope": scope})
        context = bind_new_agent_context(
            runtime, context, config=config, final_config=final_config, database_binding=database_binding
        )
        return context, executor(context)

    return AgentContinuationService(
        runtime, database_binding=database_binding, source_runtime=executor, prepare=prepare
    )
