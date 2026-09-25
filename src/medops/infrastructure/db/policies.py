"""Policy candidates, decisions, releases and the released pointer (M3-03 / DEC-012, migration 0014)."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from psycopg.types.json import Jsonb

_COLUMNS = (
    "p.policy_id::text, p.kind, p.name, p.version, p.status, p.diff, p.evidence, p.created_by, p.created_at, "
    "p.decided_by, p.decided_at, p.decision_reason, "
    "exists(select 1 from released_policies r where r.policy_id = p.policy_id)"
)
_KEYS = (
    "policy_id",
    "kind",
    "name",
    "version",
    "status",
    "diff",
    "evidence",
    "created_by",
    "created_at",
    "decided_by",
    "decided_at",
    "decision_reason",
    "released",
)


class PgPolicyStore:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    @staticmethod
    def _row(r: Any) -> dict[str, Any]:
        return dict(zip(_KEYS, r, strict=True))

    def list(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        where = "where p.status = %s" if status else ""
        params: tuple[Any, ...] = (status, limit) if status else (limit,)
        rows = self._conn.execute(
            f"select {_COLUMNS} from policies p {where} order by p.created_at desc limit %s", params
        ).fetchall()
        return [self._row(r) for r in rows]

    def get(self, policy_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            f"select {_COLUMNS} from policies p where p.policy_id = %s::uuid", (policy_id,)
        ).fetchone()
        return self._row(row) if row else None

    def insert_candidate(
        self,
        *,
        kind: str,
        name: str,
        version: str,
        diff: Mapping[str, Any],
        evidence: Mapping[str, Any],
        created_by: str,
        policy_id: str | None = None,
    ) -> str:
        pid = policy_id or uuid.uuid4().hex
        pid_uuid = str(uuid.UUID(pid)) if len(pid) == 32 else pid
        self._conn.execute(
            "insert into policies (policy_id, kind, name, version, diff, evidence, created_by) values (%s, %s, %s, %s, %s, %s, %s)",
            (pid_uuid, kind, name, version, Jsonb(dict(diff)), Jsonb(dict(evidence)), created_by),
        )
        return pid_uuid

    def decide(self, policy_id: str, *, status: str, decided_by: str, reason: str, at: datetime) -> bool:
        cur = self._conn.execute(
            "update policies set status = %s, decided_by = %s, decided_at = %s, decision_reason = %s "
            "where policy_id = %s::uuid and status = 'candidate'",
            (status, decided_by, at, reason, policy_id),
        )
        return cur.rowcount == 1

    def current_release(self, kind: str, name: str) -> str | None:
        row = self._conn.execute(
            "select policy_id::text from released_policies where kind = %s and name = %s", (kind, name)
        ).fetchone()
        return row[0] if row else None

    def release(
        self, policy_id: str, *, kind: str, name: str, canary_percent: int, actor: str, reason: str
    ) -> str | None:
        """Switch the pointer to `policy_id` (status approved -> released) and log it; returns the previous pointer."""
        previous = self.current_release(kind, name)
        cur = self._conn.execute(
            "update policies set status = 'released' where policy_id = %s::uuid and status = 'approved'", (policy_id,)
        )
        if cur.rowcount != 1:
            raise LookupError("policy is not approved")
        self._conn.execute(
            "insert into released_policies (kind, name, policy_id, updated_by) values (%s, %s, %s::uuid, %s) "
            "on conflict (kind, name) do update set policy_id = excluded.policy_id, updated_at = now(), updated_by = excluded.updated_by",
            (kind, name, policy_id, actor),
        )
        self._conn.execute(
            "insert into policy_releases (release_id, policy_id, action, canary_percent, previous_policy, actor, reason) "
            "values (%s, %s::uuid, 'release', %s, %s, %s, %s)",
            (str(uuid.uuid4()), policy_id, canary_percent, previous, actor, reason),
        )
        return previous

    def last_release(self, policy_id: str) -> dict[str, Any] | None:
        """The latest release / promote row of a policy: its current canary percentage and when it was set."""
        row = self._conn.execute(
            "select action, canary_percent, previous_policy::text, occurred_at from policy_releases "
            "where policy_id = %s::uuid and action in ('release', 'promote') order by occurred_at desc limit 1",
            (policy_id,),
        ).fetchone()
        if row is None:
            return None
        return {"action": row[0], "canary_percent": row[1], "previous_policy": row[2], "occurred_at": row[3]}

    def promote(self, policy_id: str, *, canary_percent: int, actor: str, reason: str) -> None:
        """Widen the canary of the released policy: one append-only log row; the pointer does not move (M4-09)."""
        last = self.last_release(policy_id)
        self._conn.execute(
            "insert into policy_releases (release_id, policy_id, action, canary_percent, previous_policy, actor, reason) "
            "values (%s, %s::uuid, 'promote', %s, %s, %s, %s)",
            (str(uuid.uuid4()), policy_id, canary_percent, last["previous_policy"] if last else None, actor, reason),
        )

    def rollback(self, policy_id: str, *, kind: str, name: str, actor: str, reason: str) -> str | None:
        """Atomic pointer switch back to the previous release (or removal when there is none); returns the new pointer."""
        previous_row = self._conn.execute(
            "select previous_policy::text from policy_releases where policy_id = %s::uuid and action = 'release' "
            "order by occurred_at desc limit 1",
            (policy_id,),
        ).fetchone()
        previous = previous_row[0] if previous_row else None
        cur = self._conn.execute(
            "update policies set status = 'rolled_back' where policy_id = %s::uuid and status = 'released'",
            (policy_id,),
        )
        if cur.rowcount != 1:
            raise LookupError("policy is not released")
        if previous:
            self._conn.execute(
                "update released_policies set policy_id = %s::uuid, updated_at = now(), updated_by = %s where kind = %s and name = %s",
                (previous, actor, kind, name),
            )
        else:
            self._conn.execute("delete from released_policies where kind = %s and name = %s", (kind, name))
        self._conn.execute(
            "insert into policy_releases (release_id, policy_id, action, previous_policy, actor, reason) "
            "values (%s, %s::uuid, 'rollback', %s, %s, %s)",
            (str(uuid.uuid4()), policy_id, previous, actor, reason),
        )
        return previous
