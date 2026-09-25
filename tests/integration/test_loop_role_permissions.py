"""M4-04 (record 81): the Loop database role, proven by direct database operations as the Loop LOGIN user.

The role may read the signal sources and the policy tables, open / attribute cases, open tickets and insert
*candidate* policies — and nothing else: no released pointer, no policy decision or status change, no audit or corpus
writes, no corpus reads, no schema changes. The grant matrix is pinned exactly, so any new privilege has to be added
here on purpose (INV-AUTH-05)."""

from __future__ import annotations

import uuid

import psycopg
import pytest
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

EXPECTED_GRANTS = {
    "bad_cases": {"INSERT", "SELECT", "UPDATE"},
    "document_requests": {"INSERT", "SELECT"},
    "escalations": {"SELECT"},
    "feedback": {"SELECT"},
    "policies": {"INSERT", "SELECT"},
    "policy_releases": {"SELECT"},
    "released_policies": {"SELECT"},
    "replays": {"SELECT"},
    "trace_signals": {"SELECT"},
    "traces": {"SELECT"},
}


def test_grant_matrix_is_exactly_the_documented_one(migrated):
    with psycopg.connect(migrated) as conn:
        rows = conn.execute(
            "select table_name, privilege_type from information_schema.role_table_grants where grantee = 'medops_loop_role'"
        ).fetchall()
        attrs = conn.execute(
            "select rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname = 'medops_loop_role'"
        ).fetchone()
    grants: dict[str, set[str]] = {}
    for table, privilege in rows:
        grants.setdefault(table, set()).add(privilege)
    assert grants == EXPECTED_GRANTS
    assert attrs == (False, False, False, False, False)


def test_loop_user_can_only_insert_candidates_into_policies(login_users):
    with psycopg.connect(login_users["loop"]["dsn"]) as loop:
        pid = loop.execute(
            "insert into policies (policy_id, kind, name, version, diff, evidence, created_by) values (%s, 'retrieval_params', 'hybrid', %s, %s, %s, 'loop:test') returning policy_id::text",
            (
                str(uuid.uuid4()),
                f"hybrid@test-{uuid.uuid4().hex[:6]}",
                Jsonb({"rrf_k": {"from": 60, "to": 40}}),
                Jsonb({"case_ids": []}),
            ),
        ).fetchone()[0]
        loop.commit()
        with pytest.raises(pg_errors.InsufficientPrivilege):  # RLS with-check: candidates only
            loop.execute(
                "insert into policies (policy_id, kind, name, version, diff, evidence, created_by, status) values (%s, 'prompt', 'answer_system', 'v', %s, %s, 'loop:test', 'approved')",
                (str(uuid.uuid4()), Jsonb({"text": "x"}), Jsonb({})),
            )
        loop.rollback()
        for statement, params in (
            ("update policies set status = 'approved' where policy_id = %s::uuid", (pid,)),
            ("update policies set diff = %s where policy_id = %s::uuid", (Jsonb({}), pid)),
            ("delete from policies where policy_id = %s::uuid", (pid,)),
            (
                "insert into released_policies (kind, name, policy_id, updated_by) values ('retrieval_params', 'hybrid', %s::uuid, 'loop')",
                (pid,),
            ),
            ("update released_policies set updated_by = 'loop'", ()),
            ("delete from released_policies", ()),
            (
                "insert into policy_releases (release_id, policy_id, action, canary_percent, actor, reason) values (gen_random_uuid(), %s::uuid, 'release', 0, 'loop', 'x')",
                (pid,),
            ),
        ):
            with pytest.raises(pg_errors.InsufficientPrivilege):
                loop.execute(statement, params)
            loop.rollback()


@pytest.mark.parametrize(
    "statement",
    [
        "insert into traces (trace_id, run_id, kind, principal, dept, query, outcome, reason_codes, versions, model_calls, tokens, cost_usd, duration_ms) values ('e'||repeat('0', 31), 'x', 'ask', 'p', 'MA', 'q', 'answered', '{}', '{}', 0, 0, 0, 0)",
        "update traces set outcome = 'answered'",
        "delete from traces",
        "insert into escalations (escalation_id, trace_id, principal, dept, reason_codes, query, evidence_chunk_ids, policy_version, detail, status) select 'x', trace_id, 'p', dept, '{}', 'q', '{}', 'p', 'd', 'open' from traces limit 1",
        "update escalations set status = 'closed'",
        "update escalations set resolution = 'false_alarm'",
        "insert into feedback (feedback_id, trace_id, principal, signal) select gen_random_uuid(), trace_id, 'p', 'up' from traces limit 1",
        "delete from feedback",
        "delete from replays",
        "update document_requests set status = 'accepted'",
        "delete from bad_cases",
    ],
)
def test_loop_user_has_no_other_write_path(login_users, statement):
    with psycopg.connect(login_users["loop"]["dsn"]) as loop:
        with pytest.raises(pg_errors.InsufficientPrivilege):
            loop.execute(statement)


def test_loop_user_sees_no_corpus_and_cannot_change_the_schema(migrated, login_users):
    with psycopg.connect(migrated) as conn:
        tables = {r[0] for r in conn.execute("select tablename from pg_tables where schemaname = 'public'")}
    hidden = sorted(tables - set(EXPECTED_GRANTS) - {"alembic_version"})
    assert {
        "documents",
        "chunks",
        "chunk_embeddings",
        "principals",
        "tasks",
        "trace_payloads",
        "idempotency_keys",
    } <= set(hidden)
    with psycopg.connect(login_users["loop"]["dsn"]) as loop:
        for table in hidden:
            with pytest.raises(pg_errors.InsufficientPrivilege):
                loop.execute(f"select count(*) from {table}")  # noqa: S608 - table names come from pg_tables
            loop.rollback()
        for ddl in (
            "create table loop_scratch (x int)",
            "create view loop_view as select 1",
            "alter table bad_cases add column x int",
        ):
            with pytest.raises(pg_errors.InsufficientPrivilege):
                loop.execute(ddl)
            loop.rollback()
