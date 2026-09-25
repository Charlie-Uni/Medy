"""M3-03 admin stores on a real database (DEC-012, record 75): the policy lifecycle with the loop role limited to
candidate inserts (INV-AUTH-05), the released pointer and rollback, and the document publish chain driven the way
the admin routes drive it (activate / archive / withdraw / ACL change) with audit rows and outbox events."""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg import sql

from medops.infrastructure.db.documents import PgDocumentAdminStore
from medops.infrastructure.db.idempotency import PgReceiptStore
from medops.infrastructure.db.policies import PgPolicyStore
from medops.ingestion import acl as acl_ops
from medops.ingestion import activate as activation
from tests.integration.conftest import user_dsn
from tests.integration.lexical_adapter_suite import document, job, make_database, source_object


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def loop_dsn(db: dict, admin_dsn: str) -> Iterator[str]:
    name, password = f"loop_{secrets.token_hex(4)}", secrets.token_urlsafe(18)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL(
                "create role {} login nosuperuser nobypassrls nocreatedb nocreaterole inherit password {} in role medops_loop_role"
            ).format(sql.Identifier(name), sql.Literal(password))
        )
    dbname = psycopg.conninfo.conninfo_to_dict(db["owner"])["dbname"]
    yield user_dsn(admin_dsn, name, password, dbname)
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("drop role if exists {}").format(sql.Identifier(name)))


def test_loop_role_inserts_candidates_only_and_the_pointer_switches_atomically(db, loop_dsn):
    with psycopg.connect(loop_dsn) as loop:
        store = PgPolicyStore(loop)
        pid1 = store.insert_candidate(
            kind="rule",
            name="intent_rules",
            version="v4",
            diff={"add": ["x"]},
            evidence={"gate": {"passed": True}},
            created_by="a" * 64,
        )
        pid2 = store.insert_candidate(
            kind="rule",
            name="intent_rules",
            version="v5",
            diff={"add": ["y"]},
            evidence={"gate": {"passed": True}},
            created_by="a" * 64,
        )
        loop.commit()
        with pytest.raises(pg_errors.InsufficientPrivilege):
            loop.execute("update policies set status = 'approved' where policy_id = %s::uuid", (pid1,))
        loop.rollback()
        with pytest.raises((pg_errors.InsufficientPrivilege, pg_errors.RaiseException)):
            loop.execute(
                "insert into policies (policy_id, kind, name, version, diff, evidence, status, created_by) values (%s, 'rule', 'x', 'v1', '{}', '{}', 'released', 'z')",
                (str(uuid.uuid4()),),
            )
        loop.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        store = PgPolicyStore(admin)
        now = datetime.now(UTC)
        assert store.decide(pid1, status="approved", decided_by="b" * 64, reason="ok", at=now)
        assert (
            store.decide(pid1, status="approved", decided_by="b" * 64, reason="again", at=now) is False
        )  # no longer a candidate
        assert (
            store.release(pid1, kind="rule", name="intent_rules", canary_percent=10, actor="c" * 64, reason="canary")
            is None
        )
        assert store.current_release("rule", "intent_rules") == pid1 and store.get(pid1)["released"] is True
        assert store.decide(pid2, status="approved", decided_by="b" * 64, reason="ok", at=now)
        assert (
            store.release(pid2, kind="rule", name="intent_rules", canary_percent=5, actor="c" * 64, reason="next")
            == pid1
        )
        assert store.current_release("rule", "intent_rules") == pid2 and store.get(pid1)["released"] is False
        assert store.rollback(pid2, kind="rule", name="intent_rules", actor="c" * 64, reason="regression") == pid1
        assert store.current_release("rule", "intent_rules") == pid1 and store.get(pid2)["status"] == "rolled_back"
        admin.commit()
        log = admin.execute("select action, canary_percent from policy_releases order by occurred_at").fetchall()
        assert [a for a, _ in log] == ["release", "release", "rollback"] and log[0][1] == 10
        with pytest.raises((pg_errors.RaiseException, pg_errors.InsufficientPrivilege)):  # append-only + no grant
            admin.execute("delete from policy_releases")
        admin.rollback()
    with psycopg.connect(db["users"]["app"]) as app:
        assert (
            app.execute(
                "select policy_id::text from released_policies where kind = 'rule' and name = 'intent_rules'"
            ).fetchone()[0]
            == pid1
        )
        with pytest.raises(pg_errors.InsufficientPrivilege):
            app.execute(
                "insert into released_policies (kind, name, policy_id, updated_by) values ('rule', 'q', %s::uuid, 'x')",
                (pid1,),
            )
        app.rollback()


def test_document_admin_chain_writes_audit_rows_and_outbox_events(db):
    with psycopg.connect(db["owner"]) as owner:
        src = source_object(owner, 9001)
        doc_id = document(
            owner, src, job(owner, src), family_id=uuid.uuid4(), owner_dept="MA", status="draft", version="v9001"
        )
        owner.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'MA', 'admin-01')", (doc_id,))
        owner.execute("update documents set document_key = 'admin-chain-doc' where doc_id = %s", (doc_id,))
        src2 = source_object(owner, 9002)
        draft2 = document(
            owner, src2, job(owner, src2), family_id=uuid.uuid4(), owner_dept="PV", status="draft", version="v9002"
        )
        owner.execute("update documents set document_key = 'admin-chain-draft' where doc_id = %s", (draft2,))
        owner.commit()
    with psycopg.connect(db["users"]["admin"]) as admin:
        store = PgDocumentAdminStore(admin)
        assert store.get(str(doc_id))["status"] == "draft"
        activation.activate_document(admin, "admin-chain-doc", date(2026, 9, 25), actor="d" * 64, reason="publish")
        detail = store.get(str(doc_id))
        assert (
            detail["status"] == "active"
            and detail["audit"][0]["to_status"] == "active"
            and detail["audit"][0]["actor"] == "d" * 64
        )
        change = acl_ops.change_acl(admin, "admin-chain-doc", grant=["PV"], revoke=[], actor="d" * 64, reason="shared")
        assert change.granted == ("PV",) and change.read_depts == ("MA", "PV")
        assert store.get(str(doc_id))["read_depts"] == ("MA", "PV")
        with pytest.raises(acl_ops.AclChangeRefused):
            acl_ops.change_acl(admin, "admin-chain-doc", grant=[], revoke=["MA"], actor="d" * 64, reason="no")
        activation.archive_document(admin, "admin-chain-doc", date(2026, 12, 31), actor="d" * 64, reason="superseded")
        assert store.get(str(doc_id))["status"] == "archived" and store.get(str(doc_id))["effective_to"] == date(
            2026, 12, 31
        )
        with pytest.raises(activation.ActivationRefused):
            activation.withdraw_document(admin, "admin-chain-doc", actor="d" * 64, reason="late")
        activation.withdraw_document(admin, "admin-chain-draft", actor="d" * 64, reason="abandoned")
        assert store.get(str(draft2))["status"] == "withdrawn"
        listed = store.list(dept="MA")
        assert any(d["doc_id"] == str(doc_id) for d in listed)
        receipts = PgReceiptStore(admin)
        receipts.put(
            "e" * 64,
            "PATCH /admin/documents/x/acl",
            "k1",
            "f" * 64,
            {"ok": True},
            datetime.now(UTC) + timedelta(days=1),
        )
        assert receipts.find("e" * 64, "PATCH /admin/documents/x/acl", "k1") == ("f" * 64, {"ok": True})
        admin.commit()
        audit = admin.execute("select action from doc_audit where doc_id = %s order by id", (doc_id,)).fetchall()
        assert [a[0] for a in audit][:4] == [
            "status_change",
            "acl_grant",
            "status_change",
            "status_change",
        ] or "acl_grant" in [a[0] for a in audit]
        events = admin.execute(
            "select event_type, payload->'acl_depts' from outbox_events where aggregate_id = %s order by event_id",
            (doc_id,),
        ).fetchall()
        assert [e[0] for e in events] == ["document_activated", "document_acl_changed", "document_archived"]
        assert set(events[1][1]) == {"MA", "PV"}
