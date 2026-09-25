"""Migration 0002 (M1-08): department boundary enforced by PostgreSQL for real LOGIN users.

Zero cross-department leakage, default deny without identity, drafts invisible, identity scoped to
the transaction (connection-pool reuse), LIMIT / ORDER BY never drop visible rows, read-only means no
write path, admin sees everything but cannot touch the schema or policies (baseline 3.7,
INV-AUTH-01/02/04/05).
"""

from __future__ import annotations

import secrets
import uuid
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from psycopg import errors

from medops.infrastructure.db.login_users import GROUPS, drop_users, provision
from tests.integration.conftest import user_dsn
from tests.integration.test_migrations import document, job, source_object

DEPTS = ("MA", "PV", "CO")
READ_TABLES = ("documents", "chunks", "chunk_spans", "document_acl", "source_objects")


# ------------------------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def seed(migrated: str) -> Iterator[dict]:
    """Per department: two active, one archived, one draft document (each with an ACL row for its
    department), plus one active document shared by MA and PV. Two chunks with one span each per document.
    Inserted as the admin (superuser, bypasses RLS) and removed afterwards."""
    data: dict = {"docs": {}, "chunks": {}, "shared": None, "all_docs": set()}
    counter = 1000
    with psycopg.connect(migrated) as conn:

        def make(dept: str, status: str, acl: tuple[str, ...]) -> uuid.UUID:
            nonlocal counter
            counter += 1
            src = source_object(conn, counter)
            j = job(conn, src)
            kwargs = {"family_id": uuid.uuid4(), "owner_dept": dept, "status": status, "version": f"v{counter}"}
            if status == "draft":
                doc = document(conn, src, None, **kwargs)
            else:
                doc = document(conn, src, j, effective_from=date(2026, 1, 1), **kwargs)
            for d in acl:
                conn.execute(
                    "insert into document_acl (doc_id, dept, granted_by) values (%s, %s, 'admin-01')", (doc, d)
                )
            chunk_ids = []
            for seq in range(2):
                cid = conn.execute(
                    "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, %s, 1, %s, null) returning chunk_id",
                    (doc, seq, f"{dept} {status} clause {counter}-{seq}"),
                ).fetchone()[0]
                conn.execute(
                    "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, 0, 1, 0, 5)",
                    (cid,),
                )
                chunk_ids.append(cid)
            data["chunks"][doc] = chunk_ids
            data["all_docs"].add(doc)
            return doc

        for dept in DEPTS:
            data["docs"][dept] = {
                "active": [make(dept, "active", (dept,)), make(dept, "active", (dept,))],
                "archived": [make(dept, "archived", (dept,))],
                "draft": [make(dept, "draft", (dept,))],
            }
        data["shared"] = make("MA", "active", ("MA", "PV"))
        conn.commit()
    try:
        yield data
    finally:
        with psycopg.connect(migrated, autocommit=True) as conn:
            conn.execute("select set_config('medops.actor', 'test-teardown', false)")
            conn.execute("delete from document_acl where doc_id = any(%s)", (list(data["all_docs"]),))
            conn.execute("delete from chunks where doc_id = any(%s)", (list(data["all_docs"]),))
            # non-draft documents cannot be deleted (trigger); leave them, the database is dropped at session end


def expected_visible(seed: dict, dept: str) -> set[uuid.UUID]:
    docs = set(seed["docs"][dept]["active"]) | set(seed["docs"][dept]["archived"])
    if dept in ("MA", "PV"):
        docs.add(seed["shared"])
    return docs


def rows(dsn: str, sql: str, params=None, dept: str | None = None) -> list[tuple]:
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            if dept is not None:
                conn.execute("select set_config('medops.dept', %s, true)", (dept,))
            return conn.execute(sql, params).fetchall()


def ids(dsn: str, sql: str, dept: str | None = None) -> set:
    return {r[0] for r in rows(dsn, sql, dept=dept)}


# --------------------------------------------------------------------------------------- tests


def test_group_roles_login_users_and_forced_rls(migrated, login_users):
    with psycopg.connect(migrated) as conn:
        groups = {
            r[0]: r[1:]
            for r in conn.execute(
                "select rolname, rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb from pg_roles where rolname = any(%s)",
                (list(GROUPS.values()),),
            )
        }
        assert set(groups) == set(GROUPS.values())
        for attrs in groups.values():
            assert attrs == (False, False, False, False, False), attrs
        for kind, user in login_users.items():
            row = conn.execute(
                "select rolcanlogin, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, pg_has_role(rolname, %s, 'member') from pg_roles where rolname = %s",
                (GROUPS[kind], user["name"]),
            ).fetchone()
            assert row == (True, False, False, False, False, True), (kind, row)
        forced = {
            r[0]
            for r in conn.execute(
                "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and relkind = 'r' and relrowsecurity and relforcerowsecurity"
            )
        }
        assert forced == {
            "source_objects",
            "ingestion_jobs",
            "documents",
            "chunks",
            "chunk_spans",
            "document_acl",
            "doc_audit",
            "outbox_events",  # migration 0005: admin-only transactional outbox
            "outbox_consumer_acks",
            "embedding_index_meta",  # migration 0006: vector stage (ADR-0007)
            "chunk_embeddings",
            "lexical_index_meta",  # migration 0007: production lexical index (DEC-001 final)
            "chunk_lexical_tsv",
            "operation_executions",  # migration 0008: operation-key ledger (M2-03), app writes / admin reads
            "operation_attempts",
            "principals",  # migration 0009: principal directory (M3-05), app reads / admin writes
            "tasks",  # migration 0010: asynchronous skill tasks (M3-02/04), app read/write, admin reads
            "task_attempts",
            "idempotency_keys",
            "traces",  # migration 0011: audit tables (M3-07), app appends, admin reads
            "trace_spans",
            "escalations",
            "feedback",
            "replays",  # migration 0012: trace replays (M3-08)
            "policies",  # migration 0014: policy candidates and decisions (M3-03 / DEC-012)
            "policy_releases",  # migration 0014: release / rollback log
            "released_policies",  # migration 0014: the released pointer
            "trace_payloads",  # migration 0015: encrypted replay payloads (M3-07 / DEC-013)
            "payload_access_log",  # migration 0015: who read which payload and why
            "bad_cases",  # migration 0016: Loop cases (M4-01), loop role opens / attributes, admin corrects
            "document_requests",  # migration 0017: knowledge-gap tickets (M4-05), loop opens, admin handles
        }
        owners = {r[0] for r in conn.execute("select tableowner from pg_tables where schemaname = 'public'")}
        assert owners.isdisjoint(set(GROUPS.values()) | {u["name"] for u in login_users.values()})


@pytest.mark.parametrize("kind", ["app", "readonly"])
def test_no_identity_means_no_rows_on_any_readable_table(seed, login_users, kind):
    dsn = login_users[kind]["dsn"]
    for table in READ_TABLES:
        assert rows(dsn, f"select count(*) from {table}") == [(0,)], table
    some_doc = seed["docs"]["MA"]["active"][0]
    assert rows(dsn, "select doc_id from documents where doc_id = %s", (some_doc,)) == []
    assert rows(dsn, "select chunk_id from chunks where doc_id = %s", (some_doc,)) == []
    for table in ("ingestion_jobs", "doc_audit"):
        with pytest.raises(errors.InsufficientPrivilege):
            rows(dsn, f"select count(*) from {table}")


@pytest.mark.parametrize("kind", ["app", "readonly"])
@pytest.mark.parametrize("dept", DEPTS)
def test_department_boundary_is_exact(seed, login_users, kind, dept):
    dsn = login_users[kind]["dsn"]
    visible = expected_visible(seed, dept)
    assert ids(dsn, "select doc_id from documents", dept) == visible
    assert rows(dsn, "select count(*) from documents", dept=dept) == [(len(visible),)]
    expected_chunks = {c for d in visible for c in seed["chunks"][d]}
    assert ids(dsn, "select chunk_id from chunks", dept) == expected_chunks
    assert ids(dsn, "select chunk_id from chunk_spans", dept) == expected_chunks
    sources = ids(dsn, "select source_object_id from source_objects", dept)
    assert len(sources) == len(visible)
    assert ids(dsn, "select distinct dept from document_acl", dept) == {dept}
    # no existence oracle for another department's document, not even by primary key
    other = next(d for d in DEPTS if d != dept)
    foreign = seed["docs"][other]["active"][0]
    assert rows(dsn, "select doc_id from documents where doc_id = %s", (foreign,), dept=dept) == []
    assert rows(dsn, "select count(*) from chunks where doc_id = %s", (foreign,), dept=dept) == [(0,)]
    # drafts of the own department stay invisible
    assert rows(dsn, "select count(*) from documents where status = 'draft'", dept=dept) == [(0,)]


def test_identity_is_transaction_scoped_and_cleared_on_reset(seed, login_users):
    dsn = login_users["app"]["dsn"]
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("select set_config('medops.dept', 'MA', true)")
            assert conn.execute("select count(*) from documents").fetchone()[0] == len(expected_visible(seed, "MA"))
        # SET LOCAL ended with the transaction: the same pooled connection now sees nothing
        with conn.transaction():
            assert conn.execute("select count(*) from documents").fetchone()[0] == 0
        # a session-level setting would leak across requests; RESET ALL (pool reset) clears it
        conn.execute("select set_config('medops.dept', 'PV', false)")
        conn.commit()
        assert conn.execute("select count(*) from documents").fetchone()[0] == len(expected_visible(seed, "PV"))
        conn.execute("reset all")
        conn.commit()
        assert conn.execute("select count(*) from documents").fetchone()[0] == 0
        conn.rollback()
        # DISCARD ALL, the other common pool reset, also clears it (it must run outside a transaction block)
        conn.autocommit = True
        conn.execute("select set_config('medops.dept', 'CO', false)")
        assert conn.execute("select count(*) from documents").fetchone()[0] == len(expected_visible(seed, "CO"))
        conn.execute("discard all")
        assert conn.execute("select count(*) from documents").fetchone()[0] == 0


def test_invalid_department_value_fails_closed(seed, login_users):
    dsn = login_users["app"]["dsn"]
    with pytest.raises(errors.InvalidTextRepresentation):
        rows(dsn, "select count(*) from documents", dept="HR")
    assert rows(dsn, "select count(*) from documents", dept="") == [(0,)]


def test_limit_and_order_pushdown_return_exactly_the_visible_rows(seed, login_users):
    dsn = login_users["readonly"]["dsn"]
    visible_chunks = {c for d in expected_visible(seed, "MA") for c in seed["chunks"][d]}
    assert len(visible_chunks) == 8
    top4 = rows(dsn, "select chunk_id from chunks order by chunk_id limit 4", dept="MA")
    assert len(top4) == 4 and {r[0] for r in top4} <= visible_chunks
    assert [r[0] for r in top4] == sorted(visible_chunks, key=str)[:4]
    everything = rows(dsn, "select chunk_id from chunks order by chunk_id limit 100", dept="MA")
    assert {r[0] for r in everything} == visible_chunks
    joined = rows(
        dsn,
        "select c.chunk_id from chunks c join documents d on d.doc_id = c.doc_id where d.status = 'active' order by c.chunk_id limit 3",
        dept="MA",
    )
    assert len(joined) == 3 and {r[0] for r in joined} <= visible_chunks


WRITE_ATTEMPTS = [
    (
        "insert into documents (family_id, title, doc_type, version, source_object_id, owner_dept, created_by) select gen_random_uuid(), 't', 'label', 'v', source_object_id, 'MA', 'x' from source_objects limit 1",
        None,
    ),
    ("update documents set title = 'changed'", None),
    ("delete from documents", None),
    (
        "insert into chunks (doc_id, seq, page, content, chunk_content_hash) select doc_id, 99, 1, 'x', null from documents limit 1",
        None,
    ),
    ("insert into document_acl (doc_id, dept, granted_by) select doc_id, 'CO', 'x' from documents limit 1", None),
    ("delete from document_acl", None),
    ("insert into doc_audit (doc_id, action, actor) select doc_id, 'x', 'x' from documents limit 1", None),
    ("update source_objects set integrity_status = 'failed'", None),
    ("insert into ingestion_jobs (source_object_id) select source_object_id from source_objects limit 1", None),
    ("set role medops_admin_role", None),
    ("create table public.smuggled (id int)", None),
]


@pytest.mark.parametrize("kind", ["app", "readonly"])
@pytest.mark.parametrize("statement,params", WRITE_ATTEMPTS, ids=[s[0][:28] for s in WRITE_ATTEMPTS])
def test_app_and_readonly_have_no_write_or_escalation_path(seed, login_users, kind, statement, params):
    with pytest.raises(errors.InsufficientPrivilege):
        rows(login_users[kind]["dsn"], statement, params, dept="MA")


def test_admin_sees_everything_writes_audit_and_cannot_touch_schema(seed, login_users):
    dsn = login_users["admin"]["dsn"]
    total = len(seed["all_docs"])
    with psycopg.connect(dsn) as conn:
        assert (
            conn.execute("select count(*) from documents where doc_id = any(%s)", (list(seed["all_docs"]),)).fetchone()[
                0
            ]
            == total
        )
        assert conn.execute("select rolsuper, rolbypassrls from pg_roles where rolname = current_user").fetchone() == (
            False,
            False,
        )
        draft = seed["docs"]["CO"]["draft"][0]
        job_id = conn.execute(
            "select job_id from ingestion_jobs where status = 'succeeded' and source_object_id = (select source_object_id from documents where doc_id = %s)",
            (draft,),
        ).fetchone()[0]
        activate = "update documents set status = 'active', effective_from = %s, active_ingestion_job_id = %s, parse_quality = 'trusted' where doc_id = %s"
        with pytest.raises(errors.InsufficientPrivilege, match="medops.actor"):
            with conn.transaction():
                conn.execute(activate, (date(2026, 1, 1), job_id, draft))
        with conn.transaction():
            conn.execute("select set_config('medops.actor', 'admin-user-01', true)")
            conn.execute(activate, (date(2026, 1, 1), job_id, draft))
            audit = conn.execute(
                "select from_status, to_status, actor from doc_audit where doc_id = %s", (draft,)
            ).fetchall()
            assert audit == [("draft", "active", "admin-user-01")]
            raise psycopg.Rollback()  # rolls the savepoint back and is swallowed: the seed stays unchanged
    with psycopg.connect(dsn) as conn:
        for statement in (
            "alter table documents disable row level security",
            "alter table documents no force row level security",
            "drop policy documents_dept_read on documents",
            "create policy leak on documents for select to medops_app using (true)",
            "create table public.smuggled (id int)",
            "alter role medops_app bypassrls",
            "alter role medops_app superuser",
            "create role smuggled_role login",
        ):
            try:
                with conn.transaction():
                    conn.execute(statement)
            except errors.InsufficientPrivilege:
                continue
            pytest.fail(f"admin user was not refused: {statement}")
        # GRANT without grant option is a warning-only no-op in PostgreSQL, so assert the effect instead
        with conn.transaction():
            conn.execute("grant select on documents to public")
            public_grants = conn.execute(
                "select count(*) from information_schema.table_privileges where table_name = 'documents' and grantee = 'PUBLIC'"
            ).fetchone()[0]
            assert public_grants == 0
            raise psycopg.Rollback()


def test_admin_status_change_above_was_rolled_back(seed, login_users):
    dsn = login_users["admin"]["dsn"]
    with psycopg.connect(dsn) as conn:
        draft = seed["docs"]["CO"]["draft"][0]
        assert conn.execute("select status from documents where doc_id = %s", (draft,)).fetchone() == ("draft",)


def test_provisioning_is_idempotent_and_rotates_passwords(admin_dsn, migrated):
    prefix = f"rot{secrets.token_hex(3)}"
    first = {k: secrets.token_urlsafe(16) for k in GROUPS}
    second = {k: secrets.token_urlsafe(16) for k in GROUPS}
    dbname = migrated.rsplit("/", 1)[1]
    try:
        with psycopg.connect(admin_dsn) as conn:
            names = provision(conn, prefix=prefix, passwords=first)
            conn.commit()
        psycopg.connect(user_dsn(admin_dsn, names["app"], first["app"], dbname)).close()
        with psycopg.connect(admin_dsn) as conn:
            again = provision(conn, prefix=prefix, passwords=second)
            conn.commit()
        assert again == names
        psycopg.connect(user_dsn(admin_dsn, names["app"], second["app"], dbname)).close()
        with pytest.raises(psycopg.OperationalError):
            psycopg.connect(user_dsn(admin_dsn, names["app"], first["app"], dbname))
        with psycopg.connect(admin_dsn) as conn:
            with pytest.raises(ValueError):
                provision(conn, prefix=prefix, passwords={**second, "readonly": ""})
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            drop_users(conn, prefix=prefix)
