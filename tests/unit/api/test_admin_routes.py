"""M3-03 admin routes (DEC-012, record 74): role checks per route, the document status / ACL state machine mapped to
409, the policy lifecycle (four-eyes, gate, atomic pointer, rollback) and receipt idempotency — all over in-memory
stores and fake publish-chain actions; the SQL side is covered by tests/integration/test_admin_stores.py."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.api.auth import Principal, StaticDirectory, pseudonym
from medops.domain.common import Dept
from tests.unit.api._auth_fixtures import PSEUDONYM_KEY
from tests.unit.api.test_ask_route import ISSUER_OBJ, FakeRuntime
from tests.unit.harness.test_run_ask import LABEL, FakeRetrieval

DOC = str(uuid.uuid4())
NOW = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


class MemoryDocuments:
    """Store + actions in one object: status transitions follow the database trigger's rules."""

    def __init__(self) -> None:
        self.docs = {
            DOC: {
                "doc_id": DOC,
                "document_key": "tfda-label-x",
                "family_id": str(uuid.uuid4()),
                "title": "X 仿單",
                "doc_type": "label",
                "owner_dept": "MA",
                "status": "draft",
                "version": "v1",
                "effective_from": None,
                "effective_to": None,
                "parse_quality": "trusted",
                "language": "zh-Hant",
                "created_at": NOW,
                "read_depts": ("MA",),
                "audit": [],
            }
        }
        self.events: list[str] = []

    # store
    def list(self, *, dept=None, status=None, family_id=None, limit=200):
        return [
            d
            for d in self.docs.values()
            if (not dept or d["owner_dept"] == dept) and (not status or d["status"] == status)
        ]

    def get(self, doc_id):
        return self.docs.get(doc_id)

    def document_key(self, doc_id):
        d = self.docs.get(doc_id)
        return d["document_key"] if d else None

    # actions (ValueError = refused, like ActivationRefused / AclChangeRefused)
    def _doc(self, key):
        return next(d for d in self.docs.values() if d["document_key"] == key)

    def activate(self, key, effective_from, *, actor, reason):
        d = self._doc(key)
        if d["status"] != "draft":
            raise ValueError(f"{key}: status is {d['status']}, only draft documents can be activated")
        d.update(status="active", effective_from=effective_from)
        d["audit"].insert(
            0,
            {
                "action": "status",
                "from_status": "draft",
                "to_status": "active",
                "actor": actor,
                "reason": reason,
                "occurred_at": NOW,
            },
        )
        self.events.append("document_activated")

    def archive(self, key, effective_to, *, actor, reason):
        d = self._doc(key)
        if d["status"] != "active":
            raise ValueError(f"{key}: status is {d['status']}, only active documents can be archived")
        d.update(status="archived", effective_to=effective_to)
        self.events.append("document_archived")

    def withdraw(self, key, *, actor, reason):
        d = self._doc(key)
        if d["status"] != "draft":
            raise ValueError(f"{key}: status is {d['status']}, only drafts can be withdrawn")
        d.update(status="withdrawn")
        self.events.append("document_withdrawn")

    def change_acl(self, key, *, grant, revoke, actor, reason):
        d = self._doc(key)
        if d["owner_dept"] in revoke:
            raise ValueError(f"{key}: the owner department {d['owner_dept']} keeps read access")
        before = set(d["read_depts"])
        granted = tuple(sorted(set(grant) - before))
        revoked = tuple(sorted(set(revoke) & before))
        d["read_depts"] = tuple(sorted((before | set(granted)) - set(revoked)))
        self.events.append("document_acl_changed")
        return {"granted": granted, "revoked": revoked, "read_depts": d["read_depts"]}


class MemoryPolicies:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}
        self.pointer: dict[tuple[str, str], str] = {}
        self.log: list[tuple[str, str, str | None]] = []

    def add(
        self,
        *,
        created_by: str,
        gate: bool | None = True,
        status: str = "candidate",
        kind: str = "retrieval_params",
        name: str = "hybrid",
    ) -> str:
        pid = str(uuid.uuid4())
        self.rows[pid] = {
            "policy_id": pid,
            "kind": kind,
            "name": name,
            "version": "v4",
            "status": status,
            "diff": {"rrf_k": {"from": 60, "to": 40}} if kind == "retrieval_params" else {"add": ["pattern"]},
            "evidence": {"gate": {"passed": gate}} if gate is not None else {},
            "created_by": created_by,
            "created_at": NOW,
            "decided_by": None,
            "decided_at": None,
            "decision_reason": None,
            "released": False,
        }
        return pid

    def list(self, *, status=None, limit=200):
        return [r for r in self.rows.values() if status is None or r["status"] == status]

    def get(self, policy_id):
        r = self.rows.get(policy_id)
        if r is None:
            return None
        return {**r, "released": self.pointer.get((r["kind"], r["name"])) == policy_id}

    def decide(self, policy_id, *, status, decided_by, reason, at):
        r = self.rows[policy_id]
        if r["status"] != "candidate":
            return False
        r.update(status=status, decided_by=decided_by, decided_at=at, decision_reason=reason)
        return True

    def release(self, policy_id, *, kind, name, canary_percent, actor, reason):
        previous = self.pointer.get((kind, name))
        self.rows[policy_id]["status"] = "released"
        self.pointer[(kind, name)] = policy_id
        self.log.append(("release", policy_id, previous))
        return previous

    def rollback(self, policy_id, *, kind, name, actor, reason):
        previous = next((p for a, pid, p in reversed(self.log) if a == "release" and pid == policy_id), None)
        self.rows[policy_id]["status"] = "rolled_back"
        if previous:
            self.pointer[(kind, name)] = previous
        else:
            self.pointer.pop((kind, name), None)
        self.log.append(("rollback", policy_id, previous))
        return previous


class MemoryReceipts:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], tuple[str, dict]] = {}

    def find(self, principal, route, key):
        return self.rows.get((principal, route, key))

    def put(self, principal, route, key, request_hash, receipt, expires_at):
        self.rows[(principal, route, key)] = (request_hash, dict(receipt))


class AdminRuntime(FakeRuntime):
    def __init__(self) -> None:
        super().__init__(FakeRetrieval([LABEL]), None)
        self.documents = MemoryDocuments()
        self.policies = MemoryPolicies()
        self.receipts = MemoryReceipts()

    def directory(self, conn):
        return StaticDirectory(
            {
                pseudonym("user-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=("analyst",), scopes=frozenset({"MA:read"})
                ),
                pseudonym("admin-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=("admin",), scopes=frozenset({"MA:read"})
                ),
                pseudonym("approver-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.PV, roles=("approver",), scopes=frozenset({"PV:read"})
                ),
                pseudonym("approver-2", PSEUDONYM_KEY): Principal(
                    dept=Dept.CO, roles=("approver",), scopes=frozenset({"CO:read"})
                ),
            }
        )

    @contextmanager
    def admin_connection(self):
        yield "admin-conn"

    def document_admin(self, conn):
        return self.documents, self.documents

    def policy_store(self, conn):
        return self.policies

    def receipt_store(self, conn):
        return self.receipts


def auth(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {ISSUER_OBJ.token(sub)}"}


def make() -> tuple[TestClient, AdminRuntime]:
    runtime = AdminRuntime()
    return TestClient(create_app(runtime), raise_server_exceptions=False), runtime


def test_document_routes_require_admin_and_walk_the_status_machine():
    c, rt = make()
    assert c.get("/admin/documents", headers=auth("user-1")).status_code == 403
    assert c.get("/admin/documents").status_code == 401
    listed = c.get("/admin/documents?dept=MA", headers=auth("admin-1")).json()
    assert listed["count"] == 1 and listed["items"][0]["status"] == "draft"
    # archive a draft: illegal -> 409
    r = c.patch(
        f"/admin/documents/{DOC}/status",
        json={"action": "archive", "effective_date": "2026-09-25", "reason": "x"},
        headers=auth("admin-1"),
    )
    assert r.status_code == 409 and r.json()["code"] == "status_conflict"
    # activate needs a date -> 422 without it
    assert (
        c.patch(
            f"/admin/documents/{DOC}/status", json={"action": "activate", "reason": "go"}, headers=auth("admin-1")
        ).status_code
        == 422
    )
    r = c.patch(
        f"/admin/documents/{DOC}/status",
        json={"action": "activate", "effective_date": "2026-09-25", "reason": "go"},
        headers=auth("admin-1"),
    )
    assert r.status_code == 200 and r.json()["status"] == "active" and r.json()["audit"][0]["to_status"] == "active"
    r = c.patch(
        f"/admin/documents/{DOC}/status",
        json={"action": "archive", "effective_date": "2026-12-31", "reason": "superseded"},
        headers=auth("admin-1"),
    )
    assert r.status_code == 200 and r.json()["status"] == "archived" and r.json()["effective_to"] == "2026-12-31"
    assert c.get(f"/admin/documents/{uuid.uuid4()}", headers=auth("admin-1")).status_code == 404
    assert rt.documents.events == ["document_activated", "document_archived"]


def test_document_acl_change_keeps_the_owner_and_is_idempotent_per_key():
    c, rt = make()
    body = {"grant": ["PV"], "reason": "shared product"}
    headers = {**auth("admin-1"), "Idempotency-Key": "acl-1"}
    first = c.patch(f"/admin/documents/{DOC}/acl", json=body, headers=headers)
    assert first.status_code == 200 and first.json()["granted"] == ["PV"] and first.json()["read_depts"] == ["MA", "PV"]
    again = c.patch(f"/admin/documents/{DOC}/acl", json=body, headers=headers)
    assert (
        again.status_code == 200
        and again.json() == first.json()
        and rt.documents.events.count("document_acl_changed") == 1
    )
    mismatch = c.patch(f"/admin/documents/{DOC}/acl", json={"grant": ["CO"], "reason": "other"}, headers=headers)
    assert mismatch.status_code == 422 and mismatch.json()["code"] == "idempotency_payload_mismatch"
    owner = c.patch(f"/admin/documents/{DOC}/acl", json={"revoke": ["MA"], "reason": "no"}, headers=auth("admin-1"))
    assert owner.status_code == 409
    assert (
        c.patch(
            f"/admin/documents/{DOC}/acl",
            json={"grant": ["PV"], "revoke": ["PV"], "reason": "?"},
            headers=auth("admin-1"),
        ).status_code
        == 422
    )


def test_policy_lifecycle_four_eyes_gate_release_and_rollback():
    c, rt = make()
    author = pseudonym("approver-1", PSEUDONYM_KEY)
    pid = rt.policies.add(created_by=author)
    assert c.get("/admin/policies/candidates", headers=auth("user-1")).status_code == 403
    assert c.get("/admin/policies/candidates", headers=auth("approver-2")).json()["count"] == 1
    # admins may read but not decide; the author may not decide their own candidate
    assert (
        c.post(
            f"/admin/policies/{pid}/approve", json={"decision": "approve", "reason": "ok"}, headers=auth("admin-1")
        ).status_code
        == 403
    )
    own = c.post(
        f"/admin/policies/{pid}/approve", json={"decision": "approve", "reason": "ok"}, headers=auth("approver-1")
    )
    assert own.status_code == 403 and "four-eyes" in own.json()["message"]
    # release before approval -> 409; approve -> release with canary 10 -> pointer set
    assert (
        c.post(
            f"/admin/policies/{pid}/release", json={"canary_percent": 5, "reason": "r"}, headers=auth("admin-1")
        ).status_code
        == 409
    )
    approved = c.post(
        f"/admin/policies/{pid}/approve",
        json={"decision": "approve", "reason": "looks right"},
        headers=auth("approver-2"),
    )
    assert (
        approved.status_code == 200
        and approved.json()["status"] == "approved"
        and approved.json()["decided_by"] == pseudonym("approver-2", PSEUDONYM_KEY)
    )
    assert (
        c.post(
            f"/admin/policies/{pid}/approve", json={"decision": "reject", "reason": "again"}, headers=auth("approver-2")
        ).status_code
        == 409
    )
    assert (
        c.post(
            f"/admin/policies/{pid}/release", json={"canary_percent": 50, "reason": "r"}, headers=auth("admin-1")
        ).status_code
        == 422
    )
    assert (
        c.post(
            f"/admin/policies/{pid}/release", json={"canary_percent": 10, "reason": "r"}, headers=auth("approver-2")
        ).status_code
        == 403
    )
    released = c.post(
        f"/admin/policies/{pid}/release", json={"canary_percent": 10, "reason": "canary"}, headers=auth("admin-1")
    )
    assert (
        released.status_code == 200 and released.json()["status"] == "released" and released.json()["released"] is True
    )
    # a second candidate without a gate report cannot be released
    pid2 = rt.policies.add(created_by=author, gate=None)
    c.post(f"/admin/policies/{pid2}/approve", json={"decision": "approve", "reason": "ok"}, headers=auth("approver-2"))
    gate = c.post(f"/admin/policies/{pid2}/release", json={"canary_percent": 1, "reason": "r"}, headers=auth("admin-1"))
    assert gate.status_code == 409 and gate.json()["code"] == "gate_not_passed"
    # rollback of the released policy removes the pointer (no previous release)
    rolled = c.post(f"/admin/policies/{pid}/rollback", json={"reason": "regression"}, headers=auth("admin-1"))
    assert rolled.status_code == 200 and rolled.json()["status"] == "rolled_back" and rolled.json()["released"] is False
    assert (
        c.post(f"/admin/policies/{pid}/rollback", json={"reason": "again"}, headers=auth("admin-1")).status_code == 409
    )
    assert rt.policies.log == [("release", pid, None), ("rollback", pid, None)]


def test_release_refuses_targets_the_runtime_cannot_apply():
    """M4-03: only kinds/names the policy loader applies may be released; a rule candidate can be approved but not
    released until the runtime learns to apply rule diffs (policy_target_unsupported, 409)."""
    c, rt = make()
    pid = rt.policies.add(created_by=pseudonym("approver-1", PSEUDONYM_KEY), kind="rule", name="intent_rules")
    assert (
        c.post(
            f"/admin/policies/{pid}/approve", json={"decision": "approve", "reason": "ok"}, headers=auth("approver-2")
        ).status_code
        == 200
    )
    r = c.post(f"/admin/policies/{pid}/release", json={"canary_percent": 5, "reason": "r"}, headers=auth("admin-1"))
    assert (
        r.status_code == 409
        and r.json()["code"] == "policy_target_unsupported"
        and "retrieval_params/hybrid" in r.json()["message"]
    )
    assert rt.policies.rows[pid]["status"] == "approved" and not rt.policies.pointer
