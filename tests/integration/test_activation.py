"""Draft -> active activation tool on the real schema: audited transition, INV-DATA-05 refusal, family
guard, all-or-nothing plans, and that the admin LOGIN user (not superuser) can run it."""

from __future__ import annotations

import uuid
from datetime import date

import psycopg
import pytest

from medops.ingestion.activate import ActivationRefused, activate_document, apply_plan
from tests.integration.test_migrations import document, job, source_object


def _draft(conn, n, *, quality="trusted", key=None, family=None):
    """The shared document() helper does not insert document_key; set it afterwards (not an identity column)."""
    src = source_object(conn, n)
    j = job(conn, src, quality=quality)
    doc = document(
        conn, src, j, family_id=family or uuid.uuid4(), status="draft", parse_quality=quality, version=f"v{n}"
    )
    conn.execute("update documents set document_key = %s where doc_id = %s", (key or f"doc-{n}", doc))
    return doc


def test_activation_sets_status_effective_from_and_audit_row(conn):
    _draft(conn, 7001, key="act-ok")
    result = activate_document(
        conn, "act-ok", date(2025, 1, 6), actor="reviewer-01", reason="in_text_publication: test"
    )
    row = conn.execute(
        "select status::text, effective_from, status_changed_by from documents where document_key = 'act-ok'"
    ).fetchone()
    assert row == ("active", date(2025, 1, 6), "reviewer-01")
    audit = conn.execute(
        "select from_status::text, to_status::text, actor, reason from doc_audit where doc_id = %s order by id desc limit 1",
        (result.doc_id,),
    ).fetchone()
    assert audit == ("draft", "active", "reviewer-01", "in_text_publication: test")


def test_low_trust_and_non_draft_and_unknown_are_refused_without_change(conn):
    _draft(conn, 7002, key="act-low", quality="low_trust")
    with pytest.raises(ActivationRefused, match="INV-DATA-05"):
        activate_document(conn, "act-low", date(2025, 1, 1), actor="reviewer-01", reason="r")
    assert conn.execute("select status::text from documents where document_key = 'act-low'").fetchone() == ("draft",)
    _draft(conn, 7003, key="act-twice")
    activate_document(conn, "act-twice", date(2025, 1, 1), actor="reviewer-01", reason="r")
    with pytest.raises(ActivationRefused, match="only draft"):
        activate_document(conn, "act-twice", date(2025, 1, 1), actor="reviewer-01", reason="r")
    with pytest.raises(ActivationRefused, match="unknown"):
        activate_document(conn, "act-missing", date(2025, 1, 1), actor="reviewer-01", reason="r")
    with pytest.raises(ActivationRefused, match="required"):
        activate_document(conn, "act-twice", date(2025, 1, 1), actor="", reason="r")


def test_second_version_of_a_family_is_refused_until_supersession_exists(conn):
    family = uuid.uuid4()
    _draft(conn, 7004, key="fam-v1", family=family)
    _draft(conn, 7005, key="fam-v2", family=family)
    activate_document(conn, "fam-v1", date(2024, 1, 1), actor="reviewer-01", reason="r")
    with pytest.raises(ActivationRefused, match="already has an active version"):
        activate_document(conn, "fam-v2", date(2025, 1, 1), actor="reviewer-01", reason="r")


def test_plan_is_all_or_nothing_and_skips_flagged_null_entries(conn):
    _draft(conn, 7006, key="plan-a")
    _draft(conn, 7007, key="plan-b", quality="low_trust")
    plan = [
        {"document_key": "plan-a", "effective_from": "2025-01-01", "tier": "in_text_publication", "source": "s"},
        {"document_key": "plan-b", "effective_from": None, "tier": "blocked", "flag": "low_trust"},
    ]
    done = apply_plan(conn, plan, actor="reviewer-01")
    assert [a.document_key for a in done] == ["plan-a"]
    _draft(conn, 7008, key="plan-c")
    bad = [
        {"document_key": "plan-c", "effective_from": "2025-01-01", "tier": "t", "source": "s"},
        {"document_key": "plan-b", "effective_from": "2025-01-01", "tier": "t", "source": "s"},  # low_trust -> refused
    ]
    with pytest.raises(ActivationRefused):
        apply_plan(conn, bad, actor="reviewer-01")
    assert conn.execute("select status::text from documents where document_key = 'plan-c'").fetchone() == ("draft",)
    with pytest.raises(ActivationRefused, match="without a flag"):
        apply_plan(conn, [{"document_key": "plan-c", "effective_from": None}], actor="reviewer-01")


def test_admin_login_user_can_activate_and_app_user_cannot(migrated, login_users):
    with psycopg.connect(migrated) as owner:
        _draft(owner, 7009, key="act-roles")
        owner.commit()
    with psycopg.connect(login_users["app"]["dsn"]) as app:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            activate_document(app, "act-roles", date(2025, 1, 1), actor="app", reason="r")
    with psycopg.connect(login_users["admin"]["dsn"]) as admin:
        result = activate_document(admin, "act-roles", date(2025, 1, 1), actor="admin-user-01", reason="r")
        admin.commit()
    with psycopg.connect(migrated) as owner:
        assert owner.execute("select status::text from documents where doc_id = %s", (result.doc_id,)).fetchone() == (
            "active",
        )
