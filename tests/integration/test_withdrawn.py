"""Migration 0004: `withdrawn` is a terminal state that only drafts may enter, is audited, and is invisible
to business roles."""

from __future__ import annotations

import uuid
from datetime import date

import psycopg
import pytest
from psycopg import errors

from tests.integration.test_migrations import active_document, document, job, set_actor, source_object


def test_withdrawn_is_in_the_status_enum(conn):
    labels = [r[0] for r in conn.execute("select unnest(enum_range(null::doc_status))::text")]
    assert labels == ["draft", "active", "archived", "withdrawn"]


def test_only_drafts_can_be_withdrawn_and_the_change_is_audited(conn):
    src = source_object(conn, 501)
    draft = document(conn, src, None, family_id=uuid.uuid4(), version="d")
    with pytest.raises(errors.InsufficientPrivilege, match="medops.actor"):
        with conn.transaction():
            conn.execute("update documents set status = 'withdrawn' where doc_id = %s", (draft,))
    set_actor(conn, "reviewer-01", "ingested by mistake")
    conn.execute("update documents set status = 'withdrawn' where doc_id = %s", (draft,))
    row = conn.execute("select status, status_changed_by from documents where doc_id = %s", (draft,)).fetchone()
    assert row == ("withdrawn", "reviewer-01")
    audit = conn.execute(
        "select from_status, to_status, actor, reason from doc_audit where doc_id = %s order by id", (draft,)
    ).fetchall()
    assert audit == [("draft", "withdrawn", "reviewer-01", "ingested by mistake")]
    # terminal: no further status change and no other edits
    for target in ("draft", "active", "archived"):
        with pytest.raises(errors.RestrictViolation, match="terminal"):
            with conn.transaction():
                conn.execute("update documents set status = %s where doc_id = %s", (target, draft))
    with pytest.raises(errors.RestrictViolation, match="terminal"):
        with conn.transaction():
            conn.execute("update documents set title = 'renamed' where doc_id = %s", (draft,))
    with pytest.raises(errors.RestrictViolation, match="only draft"):
        with conn.transaction():
            conn.execute("delete from documents where doc_id = %s", (draft,))
    # active and archived documents cannot be withdrawn
    active, _ = active_document(conn, 502)
    with pytest.raises(errors.CheckViolation, match="illegal status transition"):
        with conn.transaction():
            conn.execute("update documents set status = 'withdrawn' where doc_id = %s", (active,))
    conn.execute("update documents set status = 'archived' where doc_id = %s", (active,))
    with pytest.raises(errors.CheckViolation, match="illegal status transition"):
        with conn.transaction():
            conn.execute("update documents set status = 'withdrawn' where doc_id = %s", (active,))


def test_draft_to_active_still_works_after_0004(conn):
    src = source_object(conn, 503)
    j = job(conn, src)
    draft = document(conn, src, j, family_id=uuid.uuid4(), effective_from=date(2026, 1, 1))
    set_actor(conn)
    conn.execute("update documents set status = 'active' where doc_id = %s", (draft,))
    assert conn.execute("select status from documents where doc_id = %s", (draft,)).fetchone() == ("active",)


def test_withdrawn_documents_are_invisible_to_app_and_readonly(migrated, login_users):
    with psycopg.connect(migrated) as admin:
        src = source_object(admin, 504)
        withdrawn = document(admin, src, None, family_id=uuid.uuid4(), version="w", owner_dept="CO")
        admin.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'CO', 'admin-01')", (withdrawn,))
        cid = admin.execute(
            "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, 0, 1, 'withdrawn text', null) returning chunk_id",
            (withdrawn,),
        ).fetchone()[0]
        set_actor(admin, "reviewer-01")
        admin.execute("update documents set status = 'withdrawn' where doc_id = %s", (withdrawn,))
        admin.commit()
    for kind in ("app", "readonly"):
        with psycopg.connect(login_users[kind]["dsn"]) as conn, conn.transaction():
            conn.execute("select set_config('medops.dept', 'CO', true)")
            assert conn.execute("select count(*) from documents where doc_id = %s", (withdrawn,)).fetchone()[0] == 0
            assert conn.execute("select count(*) from chunks where chunk_id = %s", (cid,)).fetchone()[0] == 0
    with psycopg.connect(login_users["admin"]["dsn"]) as conn:
        assert conn.execute("select status from documents where doc_id = %s", (withdrawn,)).fetchone() == ("withdrawn",)
