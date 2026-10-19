"""Trusted Agent diagnostic entry point; fresh runs, current ACL and stable retries.

This is a server service, never an Agent tool or a public admission default.
Hosted use still requires the owner's explicit per-experiment authorization.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING, Any
from uuid import UUID

from psycopg.errors import UniqueViolation

from medops.application.agent_final_gate import FinalGateConfig
from medops.application.agent_loop_ports import AgentLoopAbort
from medops.application.agent_planning import PlannerConfig
from medops.application.agent_replay import (
    AgentReplayReport,
    AgentReplayRequest,
    AgentReplaySnapshot,
    agent_replay_report,
    input_digest,
    replay_identity,
    saved_agent_snapshot,
)
from medops.application.audit import ReplayRecord
from medops.application.metrics import has_role
from medops.bootstrap.agent_execution import AgentRuntime
from medops.bootstrap.agent_services import bind_new_agent_context, production_agent_runtime
from medops.core.canonical import canonical_hash
from medops.core.deadline import deadline_scope
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.agent_execution import AgentContext, AgentIdentity
from medops.domain.common import Sha256
from medops.domain.identity import UserContext
from medops.infrastructure.db.agent_facts import FactDatabaseBinding, PgAgentFacts
from medops.infrastructure.db.audit import PgTraceStore
from medops.infrastructure.db.final_output import acquire_output_fence, require_same_user
from medops.retrieval.integrity import database_identity

if TYPE_CHECKING:
    from medops.bootstrap.runtime import ProductionRuntime

PrepareReplay = Callable[[AgentContext, AgentIdentity, UserContext], tuple[AgentContext, AgentRuntime]]


class AgentReplayService:
    def __init__(self, runtime: ProductionRuntime, prepare: PrepareReplay):
        self.runtime, self.prepare = runtime, prepare

    def _admin(self, conn: Any, authorization: str, expected: UserContext | None = None) -> UserContext:
        acquire_output_fence(conn)
        user = self.runtime.authenticator.authenticate(authorization, self.runtime.directory(conn))
        if not has_role(user.roles, "admin"):
            raise BusinessError(ErrorCode.forbidden, "Agent replay requires the admin role")
        if expected is not None:
            require_same_user(expected, user)
        return user

    def _load(self, run_id: UUID, authorization: str, purpose: str, expected: UserContext) -> AgentReplaySnapshot:
        # Both transactions finish, including the access-log COMMIT, before
        # decrypted input can reach a binder, a model, or the diagnostic caller.
        with deadline_scope(5.0), self.runtime.connection() as identity:
            admin = self._admin(identity, authorization, expected)
            with self.runtime.restricted_connection() as restricted:
                self.runtime.validate_privileged_access(identity, restricted, admin, authorization=authorization)
                payload = self.runtime.agent_audit_reader(restricted).read(admin, str(run_id), purpose)
            source = self.runtime.trace_store(identity).read_trace(payload.trace_id)
            row = identity.execute(
                "select agent_metadata from traces where trace_id=%s", (payload.trace_id,)
            ).fetchone()
            if source is None or row is None or row[0] is None:
                raise BusinessError(ErrorCode.invalid_request, "Agent replay requires a saved business Trace")
        try:
            return saved_agent_snapshot(payload, source, row[0])
        except (ValueError, TypeError, KeyError, AttributeError):
            raise BusinessError(ErrorCode.invalid_request, "unsupported or inconsistent Agent replay source") from None

    def replay(self, source_run_id: UUID, request: AgentReplayRequest, *, authorization: str) -> AgentReplayReport:
        try:
            return self._replay(source_run_id, request, authorization=authorization)
        except (BusinessError, InfrastructureError, AgentLoopAbort):
            raise
        except Exception as exc:  # noqa: BLE001 - encrypted/model/database exception text is not a diagnostic response
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__, retryable=True) from None

    def _replay(self, source_run_id: UUID, request: AgentReplayRequest, *, authorization: str) -> AgentReplayReport:
        request = AgentReplayRequest.model_validate(request.model_dump(mode="json"))
        source_run_id = UUID(str(source_run_id))
        if len(request.reason.strip()) < 8:
            raise BusinessError(ErrorCode.invalid_request, "replay reason requires 8 non-padding characters")
        with deadline_scope(5.0), self.runtime.connection() as conn:
            admin = self._admin(conn, authorization)
            database = database_identity(conn)
        if request.mode == "original_conditions":
            raise BusinessError(
                ErrorCode.version_conflict,
                "Agent original conditions unavailable: archived corpus/index and attested loaded build required",
            )
        source = self._load(source_run_id, authorization, request.reason, admin)
        if source.provenance:
            raise BusinessError(ErrorCode.invalid_request, "a diagnostic run cannot be used as a new source")
        identity = replay_identity(request.replay_id)
        if any(getattr(identity, n) == getattr(source.context.identity, n) for n in AgentIdentity.model_fields):
            raise BusinessError(ErrorCode.version_conflict, "diagnostic identities must be fresh")
        provenance = {
            "kind": "diagnostic_replay",
            "version": "pv-agent-replay-v1",
            "replay_id": str(request.replay_id),
            "requested_by": admin.user_id,
            "source_run_id": str(source_run_id),
            "source_trace_id": source.context.identity.trace_id,
            "source_context_sha256": source.metadata.context_sha256,
            "request_sha256": canonical_hash(request.model_dump(mode="json")),
        }
        with deadline_scope(5.0), self.runtime.connection() as conn:
            self._admin(conn, authorization, admin)
            user = self.runtime.resolve_user(conn, source.context.principal.user_id)
            if (
                user is None
                or user.dept != source.context.principal.dept
                or not user.has_scopes((f"{user.dept.value}:read",))
            ):
                raise BusinessError(ErrorCode.forbidden, "the original principal is no longer authorized")
            self.runtime.bind_identity(conn, user)
            existing = conn.execute("select 1 from agent_run_control where run_id=%s", (identity.run_id,)).fetchone()
            if not existing and (
                conn.execute("select 1 from traces where trace_id=%s", (identity.trace_id,)).fetchone()
                or conn.execute("select 1 from replays where replay_id=%s", (request.replay_id,)).fetchone()
            ):
                # A surviving report/Trace still proves the identity was used,
                # even if its restricted runtime material has been purged.
                raise BusinessError(
                    ErrorCode.version_conflict, "diagnostic identity already used; saved runtime unavailable"
                )
        if existing:
            replay = self._load(identity.run_id, authorization, request.reason, admin)
            if replay.context.identity != identity or replay.provenance != (provenance,):
                raise BusinessError(ErrorCode.version_conflict, "replay ID is already bound to another command")
            # Reading only: never recover, resume, call a model or reset a budget.
            # Current permissions are checked again below before returning the report.
        else:
            context, executor = self.prepare(source.context, identity, user)
            if (
                context.identity != identity
                or context.principal != user
                or input_digest(context) != input_digest(source.context)
            ):
                raise BusinessError(ErrorCode.invalid_request, "diagnostic preparation changed the original input")
            original_resources = executor.resources

            def resources(ctx, meter):
                selected = original_resources(ctx, meter)

                def check(conn, current):
                    if database_identity(conn) != database:
                        raise BusinessError(ErrorCode.forbidden, "Agent replay requires the identity database")
                    self._admin(conn, authorization, admin)
                    selected.check_bindings(conn, current)

                return replace(selected, check_bindings=check)

            executor.resources = resources
            try:
                run = executor.new_run(context)
                with executor.start(run) as execution:
                    driver = execution.driver
                    # Durable command provenance before the FIRST provider call.
                    # A lost acknowledgement leaves an occupied run ID, never an automatic rerun.
                    with driver.connection() as conn:
                        driver._store(conn).append(
                            driver.lease,
                            "checkpoint",
                            request.replay_id,
                            provenance,
                            retained_until=driver.head.retained_until,
                        )
                    execution.execute()
            except UniqueViolation:
                raise BusinessError(
                    ErrorCode.version_conflict, "diagnostic command already started; no automatic retry"
                ) from None
            replay = self._load(identity.run_id, authorization, request.reason, admin)
            if replay.provenance != (provenance,):
                raise InfrastructureError(ErrorCode.audit_unavailable, detail="AgentReplayProvenanceMismatch")
        report = agent_replay_report(request.replay_id, source, replay)
        self._save(report, replay, admin, authorization, provenance, database)
        return report

    def _save(self, report, replay, admin, authorization, provenance, database):
        try:
            with deadline_scope(5.0), self.runtime.connection() as conn:
                self._admin(conn, authorization, admin)
                if database_identity(conn) != database:
                    raise BusinessError(ErrorCode.forbidden, "Agent replay requires the identity database")
                current = self.runtime.resolve_user(conn, replay.context.principal.user_id)
                require_same_user(replay.context.principal, current)
                assert current is not None
                self.runtime.bind_identity(conn, current)
                # Recheck current source authorization under the SAME report-commit fence.
                binding = FactDatabaseBinding(
                    fact_database_id=replay.context.versions.fact_database_id,
                    connection_identity=database_identity(conn),
                )
                facts = PgAgentFacts(conn, current, database_binding=binding)
                facts.check(replay.context)
                if replay.context.source_scope.resolution == "resolved":
                    facts.sources(replay.context)
                if replay.envelope.registry:
                    fresh = {
                        f.evidence.citation.chunk_id: f
                        for f in facts.lookup(
                            replay.context, tuple(h.evidence.citation.chunk_id for h in replay.envelope.registry)
                        )
                    }
                    if any(
                        fresh[h.evidence.citation.chunk_id].evidence != h.evidence
                        or fresh[h.evidence.citation.chunk_id].source_sha256 != h.source_sha256
                        for h in replay.envelope.registry
                    ):
                        raise BusinessError(
                            ErrorCode.version_conflict, "Agent diagnostic facts changed before report commit"
                        )
                prior = conn.execute("select report from replays where replay_id=%s", (report.replay_id,)).fetchone()
                body = report.model_dump(mode="json")
                if prior is not None:
                    if prior[0] != body:
                        raise BusinessError(ErrorCode.version_conflict, "saved Agent replay report does not match")
                    return
                PgTraceStore(conn).record_replay(
                    ReplayRecord(
                        replay_id=str(report.replay_id),
                        source_trace_id=report.source.trace_id,
                        replay_trace_id=report.replay.trace_id,
                        replay_run_id=replay.context.identity.run_id.hex,
                        requested_by=admin.user_id,
                        reason="Agent diagnostic; purpose_sha256=" + provenance["request_sha256"],
                        versions_match=report.versions_match,
                        changed=report.changed,
                        report=body,
                    )
                )
        except BusinessError:
            raise
        except Exception as exc:  # noqa: BLE001 - durable terminal remains readable; never repeat a paid run
            raise InfrastructureError(ErrorCode.audit_unavailable, detail=type(exc).__name__, retryable=True) from None


def production_agent_replay(
    runtime: ProductionRuntime,
    *,
    config: PlannerConfig,
    final_config: FinalGateConfig,
    database_binding: FactDatabaseBinding,
    rubric_sha256: Sha256,
    lease_s: float,
) -> AgentReplayService:
    """Explicit trusted configuration; no implicit planner/final profile or hosted call."""

    def prepare(old: AgentContext, identity: AgentIdentity, user: UserContext):
        context = old.model_copy(
            update={
                "identity": identity,
                "principal": user,
                "versions": old.versions.model_copy(
                    update={"fact_database_id": database_binding.fact_database_id, "rubric_sha256": rubric_sha256}
                ),
            }
        )
        with runtime.connection() as conn:
            runtime.bind_identity(conn, user)
            facts = PgAgentFacts(conn, user, database_binding=database_binding)
            if old.source_scope.requested_document is not None:
                scope = facts.resolve_scope(
                    old.source_scope.requested_document,
                    old.source_scope.requested_version,
                    query_context=old.query_context,
                )
                if old.source_scope.resolution == "resolved" and scope.resolution == "denied_or_unavailable":
                    raise BusinessError(ErrorCode.forbidden, "the original source is no longer available")
                context = context.model_copy(update={"source_scope": scope})
            elif old.source_scope.resolution == "resolved":
                raise BusinessError(ErrorCode.invalid_request, "original source selector is unavailable")
        context = bind_new_agent_context(
            runtime, context, config=config, final_config=final_config, database_binding=database_binding
        )
        return context, production_agent_runtime(
            runtime,
            context,
            config=config,
            final_config=final_config,
            database_binding=database_binding,
            lease_s=lease_s,
        )

    return AgentReplayService(runtime, prepare)
