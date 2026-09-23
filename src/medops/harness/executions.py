"""Operation-key persistence (baseline 3.2, M2-03): claim before run, reuse a succeeded result, record every
attempt separately, and keep replays apart from production.

The harness computes a stable `operation_key` per node (scope + run_id + node + canonical input and versions).
An `ExecutionStore` turns that key into an idempotency guarantee: `claim` inserts the key before the body runs
(a second worker sees `in_flight`), a repeated call with the same key gets the stored result (`reused`) and
never re-executes the side effects, a failed or stale claim can be retried (`retry`, claim_no + 1). Production
runs use `run_id == trace_id`; a replay passes its own `replay_run_id`, which changes every key, so a replay
can never be short-circuited by the production cache (M3-08).

The result stored per node is the state delta (fields the node changed, JSON), re-applied through
`AgentState.advance`, so reuse goes through the same invariants as a fresh execution.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from psycopg.types.json import Jsonb

from medops.domain.state import AgentState
from medops.harness.contracts import NodeAttempt

ClaimKind = Literal["new", "retry", "reused", "in_flight"]
STALE_CLAIM_S = 300.0  # a `running` claim older than this belongs to a dead worker and may be re-claimed


def run_kind(run_id: str, trace_id: str) -> str:
    return "production" if run_id == trace_id else "replay"


@dataclass(frozen=True)
class ExecutionClaim:
    kind: ClaimKind
    claim_no: int
    result: Mapping[str, Any] | None = None


class ExecutionStore(Protocol):
    def claim(
        self,
        *,
        operation_key: str,
        operation_scope: str,
        run_id: str,
        trace_id: str,
        node_name: str,
        versions: Mapping[str, Any],
        now: datetime,
    ) -> ExecutionClaim: ...

    def record_attempts(self, claim_no: int, attempts: Sequence[NodeAttempt]) -> None: ...

    def complete(self, operation_key: str, result: Mapping[str, Any], now: datetime) -> None: ...

    def fail(self, operation_key: str, error_code: str, now: datetime) -> None: ...


def state_delta(before: AgentState, after: AgentState) -> dict[str, Any]:
    old = before.model_dump(mode="json")
    new = after.model_dump(mode="json")
    return {name: value for name, value in new.items() if value != old.get(name)}


def apply_delta(state: AgentState, delta: Mapping[str, Any]) -> AgentState:
    """The stored delta is applied on top of the pre-node state and re-validated as a whole. `advance()` is
    not used here: its downstream-reset rule would blank fields the node left unchanged (e.g. Answer's
    re-verification changes `verify_result` but keeps the Safety decision), which a replayed delta must keep."""
    return AgentState.model_validate({**state.model_dump(mode="json"), **dict(delta)})


# ------------------------------------------------------------------------------------ in-memory (tests)


@dataclass
class _Row:
    operation_scope: str
    run_id: str
    trace_id: str
    run_kind: str
    node_name: str
    versions: dict[str, Any]
    status: str
    claim_no: int
    claimed_at: datetime
    result: dict[str, Any] | None = None
    error_code: str | None = None
    finished_at: datetime | None = None


@dataclass
class InMemoryExecutionStore:
    stale_after_s: float = STALE_CLAIM_S
    rows: dict[str, _Row] = field(default_factory=dict)
    attempts: list[tuple[int, NodeAttempt]] = field(default_factory=list)

    def claim(self, *, operation_key, operation_scope, run_id, trace_id, node_name, versions, now) -> ExecutionClaim:
        row = self.rows.get(operation_key)
        if row is None:
            self.rows[operation_key] = _Row(
                operation_scope,
                run_id,
                trace_id,
                run_kind(run_id, trace_id),
                node_name,
                dict(versions),
                "running",
                1,
                now,
            )
            return ExecutionClaim("new", 1)
        if row.status == "succeeded":
            return ExecutionClaim("reused", row.claim_no, row.result)
        stale = row.status == "running" and (now - row.claimed_at).total_seconds() > self.stale_after_s
        if row.status == "failed" or stale:
            row.status, row.claim_no, row.claimed_at = "running", row.claim_no + 1, now
            row.error_code, row.finished_at = None, None
            return ExecutionClaim("retry", row.claim_no)
        return ExecutionClaim("in_flight", row.claim_no)

    def record_attempts(self, claim_no: int, attempts: Sequence[NodeAttempt]) -> None:
        self.attempts.extend((claim_no, a) for a in attempts)

    def complete(self, operation_key: str, result: Mapping[str, Any], now: datetime) -> None:
        row = self.rows[operation_key]
        row.status, row.result, row.finished_at = "succeeded", dict(result), now

    def fail(self, operation_key: str, error_code: str, now: datetime) -> None:
        row = self.rows[operation_key]
        row.status, row.error_code, row.finished_at = "failed", error_code, now


# ------------------------------------------------------------------------------------ PostgreSQL


class PgExecutionStore:
    """Backed by `operation_executions` / `operation_attempts` (migration 0008), written under the application
    role inside the caller's transaction. `claim` relies on the primary key: the insert either wins or sees
    the existing row locked `for update`, so two workers never both run the same operation."""

    def __init__(self, conn: Any, *, stale_after_s: float = STALE_CLAIM_S) -> None:
        self._conn = conn
        self._stale = stale_after_s

    def claim(self, *, operation_key, operation_scope, run_id, trace_id, node_name, versions, now) -> ExecutionClaim:
        inserted = self._conn.execute(
            """
            insert into operation_executions
                (operation_key, operation_scope, run_id, trace_id, run_kind, node_name, versions, status, claimed_at)
            values (%(key)s, %(scope)s, %(run)s, %(trace)s, %(kind)s, %(node)s, %(versions)s, 'running', %(now)s)
            on conflict (operation_key) do nothing
            returning claim_no
            """,
            {
                "key": operation_key,
                "scope": operation_scope,
                "run": run_id,
                "trace": trace_id,
                "kind": run_kind(run_id, trace_id),
                "node": node_name,
                "versions": Jsonb(dict(versions)),
                "now": now,
            },
        ).fetchone()
        if inserted is not None:
            return ExecutionClaim("new", int(inserted[0]))
        row = self._conn.execute(
            "select status, claim_no, result, claimed_at from operation_executions where operation_key = %s for update",
            (operation_key,),
        ).fetchone()
        status, claim_no, result, claimed_at = row
        if status == "succeeded":
            return ExecutionClaim("reused", int(claim_no), result)
        age = (now - claimed_at.astimezone(UTC)).total_seconds() if claimed_at.tzinfo else float("inf")
        if status == "failed" or (status == "running" and age > self._stale):
            new_no = self._conn.execute(
                """
                update operation_executions
                   set status = 'running', claim_no = claim_no + 1, claimed_at = %(now)s, error_code = null, finished_at = null
                 where operation_key = %(key)s
                returning claim_no
                """,
                {"key": operation_key, "now": now},
            ).fetchone()[0]
            return ExecutionClaim("retry", int(new_no))
        return ExecutionClaim("in_flight", int(claim_no))

    def record_attempts(self, claim_no: int, attempts: Sequence[NodeAttempt]) -> None:
        if not attempts:
            return
        with self._conn.cursor() as cur:
            cur.executemany(
                """
                insert into operation_attempts
                    (operation_key, claim_no, attempt, outcome, error_code, detail, started_at, duration_ms)
                values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        a.operation_key,
                        claim_no,
                        a.attempt,
                        a.outcome,
                        a.error_code,
                        a.detail,
                        a.started_at,
                        a.duration_ms,
                    )
                    for a in attempts
                ],
            )

    def complete(self, operation_key: str, result: Mapping[str, Any], now: datetime) -> None:
        self._conn.execute(
            "update operation_executions set status = 'succeeded', result = %s, finished_at = %s where operation_key = %s and status = 'running'",
            (Jsonb(dict(result)), now, operation_key),
        )

    def fail(self, operation_key: str, error_code: str, now: datetime) -> None:
        self._conn.execute(
            "update operation_executions set status = 'failed', error_code = %s, finished_at = %s where operation_key = %s and status = 'running'",
            (error_code, now, operation_key),
        )
