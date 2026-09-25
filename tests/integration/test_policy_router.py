"""Migration 0018 + the release state the runtime routes on (M4-09 / M4-10): release with a canary share, promote it,
release a successor (previous kept for the remaining traffic), roll back — and what the app role's loader sees after
each atomic switch."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import psycopg
from psycopg.types.json import Jsonb

from medops.application.policy_loader import load_release_state
from medops.infrastructure.db.policies import PgPolicyStore

APPROVER = "d" * 32


def _candidate(store: PgPolicyStore, rrf_to: float) -> str:
    return store.insert_candidate(
        kind="retrieval_params",
        name="hybrid",
        version=f"hybrid@drill-{uuid.uuid4().hex[:6]}",
        diff={"rrf_k": {"from": 60.0, "to": rrf_to}},
        evidence={"case_ids": [], "gate": {"passed": True, "drill": True}},
        created_by="loop:test",
    )


def test_release_promote_successor_and_rollback_as_the_app_role_sees_them(migrated, login_users):
    app_dsn = login_users["app"]["dsn"]
    with psycopg.connect(login_users["admin"]["dsn"]) as admin:
        store = PgPolicyStore(admin)
        first = _candidate(store, 40.0)
        assert store.decide(first, status="approved", decided_by=APPROVER, reason="t", at=datetime.now(UTC))
        store.release(first, kind="retrieval_params", name="hybrid", canary_percent=10, actor=APPROVER, reason="canary")
        admin.commit()
        with psycopg.connect(app_dsn) as app:
            state = load_release_state(app)
        target = next(t for t in state.targets if (t.kind, t.name) == ("retrieval_params", "hybrid"))
        assert target.canary_percent == 10 and target.previous is None and target.current.policy_id == first
        # the remaining 90% run on the constants; canary principals get the new policy; the split is stable
        sides = {state.for_principal(f"p{i}").policy_version("b") for i in range(300)}
        assert sides == {"b", "b+canary:" + first.replace("-", "")[:8]}
        # promote widens the share; the pointer is unchanged; the log grows by one promote row
        store.promote(first, canary_percent=100, actor=APPROVER, reason="全量")
        admin.commit()
        with psycopg.connect(app_dsn) as app:
            state = load_release_state(app)
        assert next(t for t in state.targets if t.current.policy_id == first).canary_percent == 100
        assert {state.for_principal(f"p{i}").policy_version("b") for i in range(50)} == {
            "b+rel:" + first.replace("-", "")[:8]
        }
        assert store.last_release(first) == {
            "action": "promote",
            "canary_percent": 100,
            "previous_policy": None,
            "occurred_at": store.last_release(first)["occurred_at"],
        }
        # a successor at 10%: its previous is the first policy, which the other 90% keep using
        second = _candidate(store, 30.0)
        store.decide(second, status="approved", decided_by=APPROVER, reason="t", at=datetime.now(UTC))
        store.release(second, kind="retrieval_params", name="hybrid", canary_percent=10, actor=APPROVER, reason="next")
        admin.commit()
        with psycopg.connect(app_dsn) as app:
            state = load_release_state(app)
        target = next(t for t in state.targets if (t.kind, t.name) == ("retrieval_params", "hybrid"))
        assert target.current.policy_id == second and target.previous is not None and target.previous.policy_id == first
        sides = {state.for_principal(f"p{i}").policy_version("b") for i in range(300)}
        assert sides == {"b+rel:" + first.replace("-", "")[:8], "b+canary:" + second.replace("-", "")[:8]}
        # rollback: one atomic switch back to the first policy at 100%
        store.rollback(second, kind="retrieval_params", name="hybrid", actor=APPROVER, reason="drill")
        admin.commit()
        with psycopg.connect(app_dsn) as app:
            state = load_release_state(app)
        target = next(t for t in state.targets if (t.kind, t.name) == ("retrieval_params", "hybrid"))
        assert target.current.policy_id == first and target.canary_percent == 100
        # the append-only log recorded release / promote / release / rollback
        actions = [
            r[0]
            for r in admin.execute(
                "select action from policy_releases where policy_id in (%s::uuid, %s::uuid) order by occurred_at",
                (first, second),
            ).fetchall()
        ]
        assert actions == ["release", "promote", "release", "rollback"]
        # clean the pointer for other tests
        store.rollback(first, kind="retrieval_params", name="hybrid", actor=APPROVER, reason="cleanup")
        admin.commit()
        admin.execute("select 1")
        with psycopg.connect(app_dsn) as app:
            assert load_release_state(app).targets == ()
    _ = Jsonb  # imported for parity with the other store tests
