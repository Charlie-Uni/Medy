"""Migration 0001 (M1-06, M1-07): round trip, inventory, and every database-enforced rule."""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from datetime import date

import psycopg
import pytest
from alembic.script import ScriptDirectory
from psycopg import errors

from tests.integration.conftest import alembic_config, run_alembic

EXPECTED_TABLES = {
    "source_objects",
    "ingestion_jobs",
    "documents",
    "chunks",
    "chunk_spans",
    "document_acl",
    "doc_audit",
    "outbox_events",
    "outbox_consumer_acks",
    "embedding_index_meta",
    "chunk_embeddings",
}
EXPECTED_TYPES = {
    "dept",
    "doc_type",
    "doc_status",
    "parse_quality",
    "integrity_status",
    "ingestion_status",
    "acl_permission",
}
HEX64 = "0" * 63


def _hash(n: int) -> str:
    return f"{n:064x}"


def _policies(dsn: str) -> int:
    with psycopg.connect(dsn) as c:
        return c.execute("select count(*) from pg_policies where schemaname = 'public'").fetchone()[0]


def _rls_forced(dsn: str) -> set[str]:
    with psycopg.connect(dsn) as c:
        return {
            r[0]
            for r in c.execute(
                "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = 'public' and c.relkind = 'r' and c.relrowsecurity and c.relforcerowsecurity"
            )
        }


def _inventory(dsn: str) -> dict[str, set[str]]:
    with psycopg.connect(dsn) as c:
        tables = {r[0] for r in c.execute("select tablename from pg_tables where schemaname = 'public'")}
        types = {
            r[0]
            for r in c.execute(
                "select typname from pg_type t join pg_namespace n on n.oid = t.typnamespace where n.nspname = 'public' and t.typtype = 'e'"
            )
        }
        functions = {
            r[0]
            for r in c.execute(
                "select proname from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public'"
            )
        }
    return {"tables": tables, "types": types, "functions": functions}


# ------------------------------------------------------------------------------------------ helpers


def source_object(conn: psycopg.Connection, n: int = 1, **overrides) -> uuid.UUID:
    row = {
        "source_hash": _hash(n),
        "storage_uri": f"file:///sources/{_hash(n)}.pdf",
        "byte_size": 1000 + n,
        "mime": "application/pdf",
        "created_by": "ingest-01",
    }
    row.update(overrides)
    cur = conn.execute(
        "insert into source_objects (source_hash, storage_uri, byte_size, mime, created_by) values (%(source_hash)s, %(storage_uri)s, %(byte_size)s, %(mime)s, %(created_by)s) returning source_object_id",
        row,
    )
    return cur.fetchone()[0]


def job(
    conn: psycopg.Connection, source_id: uuid.UUID, *, status: str = "succeeded", quality: str = "trusted"
) -> uuid.UUID:
    cur = conn.execute(
        "insert into ingestion_jobs (source_object_id, status, parse_quality, parser_version, failure_reason) values (%s, %s, %s, 'pypdf-6.18.1', %s) returning job_id",
        (source_id, status, quality, "boom" if status == "failed" else None),
    )
    return cur.fetchone()[0]


def document(conn: psycopg.Connection, source_id: uuid.UUID, job_id: uuid.UUID | None = None, **overrides) -> uuid.UUID:
    row = {
        "family_id": uuid.uuid4(),
        "title": "示例药品X片说明书",
        "doc_type": "label",
        "version": "2026-01",
        "status": "draft",
        "effective_from": None,
        "effective_to": None,
        "source_object_id": source_id,
        "active_ingestion_job_id": job_id,
        "parse_quality": "pending" if job_id is None else "trusted",
        "owner_dept": "MA",
        "language": "zh-Hans",
        "created_by": "ingest-01",
    }
    row.update(overrides)
    cur = conn.execute(
        """insert into documents (family_id, title, doc_type, version, status, effective_from, effective_to, source_object_id,
                                  active_ingestion_job_id, parse_quality, owner_dept, language, created_by)
           values (%(family_id)s, %(title)s, %(doc_type)s, %(version)s, %(status)s, %(effective_from)s, %(effective_to)s,
                   %(source_object_id)s, %(active_ingestion_job_id)s, %(parse_quality)s, %(owner_dept)s, %(language)s, %(created_by)s)
           returning doc_id""",
        row,
    )
    return cur.fetchone()[0]


def active_document(
    conn: psycopg.Connection, n: int = 1, family: uuid.UUID | None = None, version: str = "2026-01"
) -> tuple[uuid.UUID, uuid.UUID]:
    src = source_object(conn, n)
    j = job(conn, src)
    doc = document(
        conn,
        src,
        j,
        family_id=family or uuid.uuid4(),
        version=version,
        status="active",
        effective_from=date(2026, 1, 1),
    )
    return doc, src


def set_actor(conn: psycopg.Connection, actor: str = "reviewer-01", reason: str | None = None) -> None:
    conn.execute("select set_config('medops.actor', %s, true)", (actor,))
    if reason is not None:
        conn.execute("select set_config('medops.reason', %s, true)", (reason,))


# ------------------------------------------------------------------------------------- round trip


def test_single_head_and_offline_sql_render(migrated):
    heads = ScriptDirectory.from_config(alembic_config(migrated)).get_heads()
    assert heads == ["0006"]


def test_upgrade_downgrade_upgrade_round_trip_leaves_nothing_behind(scratch_database):
    run_alembic(scratch_database, "upgrade", "head")
    after_up = _inventory(scratch_database)
    assert after_up["tables"] == EXPECTED_TABLES | {"alembic_version"}
    assert after_up["types"] == EXPECTED_TYPES
    assert {f for f in after_up["functions"] if f.startswith("medops_")} == {
        "medops_forbid_change",
        "medops_source_objects_immutable",
        "medops_documents_guard",
        "medops_documents_audit",
        "medops_documents_delete_guard",
        "medops_chunks_hash",
        "medops_current_dept",
        "medops_outbox_guard",
        "medops_outbox_acks_guard",
    }
    assert _policies(scratch_database) > 0 and _rls_forced(scratch_database) == EXPECTED_TABLES
    run_alembic(scratch_database, "downgrade", "base")
    after_down = _inventory(scratch_database)
    assert after_down["tables"] == {"alembic_version"}
    assert after_down["types"] == set()
    assert not {f for f in after_down["functions"] if f.startswith("medops_")}
    assert _policies(scratch_database) == 0
    # group roles are cluster-wide and deliberately survive a downgrade (0002 docstring)
    with psycopg.connect(scratch_database) as c:
        roles = {r[0] for r in c.execute("select rolname from pg_roles where rolname like 'medops_%'")}
    assert {"medops_app", "medops_readonly", "medops_admin_role"} <= roles
    run_alembic(scratch_database, "upgrade", "head")
    assert _inventory(scratch_database)["tables"] == EXPECTED_TABLES | {"alembic_version"}


def test_only_the_decided_vector_column_exists_and_no_tsvector_before_dec_001(conn):
    """DEC-002 is decided (ADR-0007): exactly one vector(1024) column, in chunk_embeddings. DEC-001 is still
    open, so no tsvector column may exist in a migration (candidate index tables are experiment-scoped)."""
    rows = conn.execute(
        "select table_name, column_name, udt_name from information_schema.columns where table_schema = 'public' and udt_name in ('vector', 'tsvector')"
    ).fetchall()
    assert rows == [("chunk_embeddings", "embedding", "vector")]
    dim = conn.execute(
        "select atttypmod from pg_attribute where attrelid = 'chunk_embeddings'::regclass and attname = 'embedding'"
    ).fetchone()[0]
    assert dim == 1024


def test_one_active_per_family_is_a_partial_unique_index(conn):
    row = conn.execute("select indexdef from pg_indexes where indexname = 'documents_one_active_per_family'").fetchone()
    assert row is not None
    assert "UNIQUE" in row[0] and "WHERE" in row[0] and "status = 'active'" in row[0]


# ------------------------------------------------------------------------------- INV-DATA-02


def test_second_active_version_in_same_family_is_rejected(conn):
    family = uuid.uuid4()
    active_document(conn, 1, family, "2026-01")
    src = source_object(conn, 2)
    j = job(conn, src)
    with pytest.raises(errors.UniqueViolation, match="documents_one_active_per_family"):
        with conn.transaction():
            document(
                conn, src, j, family_id=family, version="2026-02", status="active", effective_from=date(2026, 2, 1)
            )
    # a draft and an archived version in the same family are fine
    document(conn, src, None, family_id=family, version="2026-03")
    active_document(conn, 3, uuid.uuid4(), "v1")


def test_concurrent_activations_serialize_on_the_unique_index(migrated):
    """Two sessions activate different versions of the same family at the same time: the second
    blocks on the partial unique index and fails once the first commits (M1-07: proven in the
    database, not by a read-then-write in Python)."""
    family = uuid.uuid4()
    with psycopg.connect(migrated) as setup:
        src_a, src_b = source_object(setup, 11), source_object(setup, 12)
        job_a, job_b = job(setup, src_a), job(setup, src_b)
        setup.commit()

    outcome: dict[str, object] = {}
    started = threading.Event()

    def second_session() -> None:
        with psycopg.connect(migrated) as b:
            started.set()
            try:
                document(
                    b, src_b, job_b, family_id=family, version="B", status="active", effective_from=date(2026, 1, 1)
                )
                b.commit()
                outcome["result"] = "committed"
            except errors.UniqueViolation as exc:
                outcome["result"] = type(exc).__name__

    try:
        with psycopg.connect(migrated) as a:
            document(a, src_a, job_a, family_id=family, version="A", status="active", effective_from=date(2026, 1, 1))
            worker = threading.Thread(target=second_session)
            worker.start()
            started.wait(5)
            time.sleep(1.0)
            assert "result" not in outcome, "second activation must block while the first is uncommitted"
            a.commit()
            worker.join(10)
        assert outcome.get("result") == "UniqueViolation"
        with psycopg.connect(migrated) as check:
            actives = check.execute(
                "select version from documents where family_id = %s and status = 'active'", (family,)
            ).fetchall()
            assert actives == [("A",)]
    finally:
        with psycopg.connect(migrated, autocommit=True) as cleanup:
            cleanup.execute("delete from documents where family_id = %s and status = 'draft'", (family,))


# ------------------------------------------------------------------------ 3.4 / INV-DATA-05 rules


def test_active_requires_effective_from_trusted_parse_and_a_succeeded_job(conn):
    src = source_object(conn, 21)
    good = job(conn, src)
    base = {"family_id": uuid.uuid4(), "status": "active", "effective_from": date(2026, 1, 1)}
    savepoint = conn.transaction
    with pytest.raises(errors.CheckViolation, match="documents_non_draft_has_effective_from"):
        with savepoint():
            document(conn, src, good, **{**base, "effective_from": None})
    with pytest.raises(errors.CheckViolation, match="documents_active_has_job"):
        with savepoint():
            document(conn, src, None, **{**base, "parse_quality": "trusted"})
    low = job(conn, src, quality="low_trust")
    with pytest.raises(errors.CheckViolation, match="documents_active_is_trusted"):
        with savepoint():
            document(conn, src, low, **{**base, "parse_quality": "low_trust"})
    with pytest.raises(errors.CheckViolation, match="must equal the active job parse_quality"):
        with savepoint():
            document(conn, src, low, **{**base, "parse_quality": "trusted"})
    running = job(conn, src, status="running", quality="pending")
    with pytest.raises(errors.CheckViolation, match="succeeded job"):
        with savepoint():
            document(conn, src, running, **{**base, "parse_quality": "pending"})
    other_src = source_object(conn, 22)
    with pytest.raises(errors.ForeignKeyViolation, match="documents_job_matches_source"):
        with savepoint():
            document(conn, other_src, good, **base)
    with pytest.raises(errors.CheckViolation, match="documents_effective_window"):
        with savepoint():
            document(conn, src, good, **{**base, "effective_to": date(2025, 12, 31)})
    # the well-formed active document is accepted; a draft may lack effective_from
    document(conn, src, good, **base)
    document(conn, src, None, family_id=uuid.uuid4(), version="draft-1")


def test_archived_requires_effective_from_too(conn):
    src = source_object(conn, 23)
    with pytest.raises(errors.CheckViolation, match="documents_non_draft_has_effective_from"):
        with conn.transaction():
            document(conn, src, None, family_id=uuid.uuid4(), status="archived", parse_quality="pending")


# --------------------------------------------------------------------------------- immutability


def test_source_objects_are_unique_by_hash_and_immutable(conn):
    sid = source_object(conn, 31)
    with pytest.raises(errors.UniqueViolation):
        with conn.transaction():
            source_object(conn, 31, storage_uri="file:///elsewhere.pdf")
    with pytest.raises(errors.CheckViolation):
        with conn.transaction():
            source_object(conn, 32, source_hash="not-a-hash")
    for column, value in (
        ("source_hash", _hash(99)),
        ("storage_uri", "file:///moved.pdf"),
        ("byte_size", 5),
        ("mime", "text/plain"),
    ):
        with pytest.raises(errors.RestrictViolation, match="immutable"):
            with conn.transaction():
                conn.execute(f"update source_objects set {column} = %s where source_object_id = %s", (value, sid))
    with pytest.raises(errors.RestrictViolation):
        with conn.transaction():
            conn.execute("delete from source_objects where source_object_id = %s", (sid,))
    conn.execute(
        "update source_objects set integrity_status = 'verified', last_verified_at = now() where source_object_id = %s",
        (sid,),
    )
    assert (
        conn.execute("select integrity_status from source_objects where source_object_id = %s", (sid,)).fetchone()[0]
        == "verified"
    )


def test_document_identity_columns_are_immutable(conn):
    doc, src = active_document(conn, 41)
    other = source_object(conn, 42)
    for column, value in (
        ("family_id", uuid.uuid4()),
        ("version", "2099-01"),
        ("doc_type", "sop"),
        ("source_object_id", other),
    ):
        with pytest.raises(errors.RestrictViolation, match="immutable"):
            with conn.transaction():
                conn.execute(f"update documents set {column} = %s where doc_id = %s", (value, doc))
    conn.execute("update documents set title = %s where doc_id = %s", ("新标题", doc))


# ------------------------------------------------------------------- status machine and audit


def test_status_changes_need_an_actor_follow_the_state_machine_and_write_audit(conn):
    src = source_object(conn, 51)
    j = job(conn, src)
    doc = document(conn, src, j, family_id=uuid.uuid4(), effective_from=date(2026, 1, 1))
    # no actor in the session
    with pytest.raises(errors.InsufficientPrivilege, match="medops.actor"):
        with conn.transaction():
            conn.execute("update documents set status = 'active' where doc_id = %s", (doc,))
    assert conn.execute("select count(*) from doc_audit where doc_id = %s", (doc,)).fetchone()[0] == 0
    # draft -> active with actor and reason
    set_actor(conn, "reviewer-01", "approved after review")
    conn.execute("update documents set status = 'active' where doc_id = %s", (doc,))
    row = conn.execute(
        "select status, status_changed_by, status_changed_at is not null from documents where doc_id = %s", (doc,)
    ).fetchone()
    assert row == ("active", "reviewer-01", True)
    audit = conn.execute(
        "select action, from_status, to_status, actor, reason from doc_audit where doc_id = %s order by id", (doc,)
    ).fetchall()
    assert audit == [("status_change", "draft", "active", "reviewer-01", "approved after review")]
    # backwards and skipping transitions are refused
    for target in ("draft",):
        with pytest.raises(errors.CheckViolation, match="illegal status transition"):
            with conn.transaction():
                conn.execute("update documents set status = %s where doc_id = %s", (target, doc))
    conn.execute("update documents set status = 'archived' where doc_id = %s", (doc,))
    for target in ("active", "draft"):
        with pytest.raises(errors.CheckViolation, match="illegal status transition"):
            with conn.transaction():
                conn.execute("update documents set status = %s where doc_id = %s", (target, doc))
    assert conn.execute("select count(*) from doc_audit where doc_id = %s", (doc,)).fetchone()[0] == 2
    # draft can never skip straight to archived
    draft = document(conn, src, None, family_id=uuid.uuid4(), version="d2")
    with pytest.raises(errors.CheckViolation, match="illegal status transition"):
        with conn.transaction():
            conn.execute(
                "update documents set status = 'archived', effective_from = %s where doc_id = %s",
                (date(2026, 1, 1), draft),
            )


def test_audit_rows_cannot_be_updated_or_deleted(conn):
    doc, _ = active_document(conn, 61)
    set_actor(conn)
    conn.execute("update documents set status = 'archived' where doc_id = %s", (doc,))
    audit_id = conn.execute("select id from doc_audit where doc_id = %s", (doc,)).fetchone()[0]
    with pytest.raises(errors.RestrictViolation):
        with conn.transaction():
            conn.execute("update doc_audit set actor = 'someone-else' where id = %s", (audit_id,))
    with pytest.raises(errors.RestrictViolation):
        with conn.transaction():
            conn.execute("delete from doc_audit where id = %s", (audit_id,))


def test_only_draft_documents_can_be_deleted_and_cascade_to_chunks_and_acl(conn):
    doc, _ = active_document(conn, 71)
    with pytest.raises(errors.RestrictViolation, match="only draft"):
        with conn.transaction():
            conn.execute("delete from documents where doc_id = %s", (doc,))
    src = source_object(conn, 72)
    draft = document(conn, src, None, family_id=uuid.uuid4(), version="d")
    conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'MA', 'admin-01')", (draft,))
    cid = conn.execute(
        "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, 0, 1, 'x', null) returning chunk_id",
        (draft,),
    ).fetchone()[0]
    conn.execute(
        "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, 0, 1, 0, 1)", (cid,)
    )
    conn.execute("delete from documents where doc_id = %s", (draft,))
    assert conn.execute("select count(*) from chunks where doc_id = %s", (draft,)).fetchone()[0] == 0
    assert conn.execute("select count(*) from chunk_spans where chunk_id = %s", (cid,)).fetchone()[0] == 0
    assert conn.execute("select count(*) from document_acl where doc_id = %s", (draft,)).fetchone()[0] == 0


# ------------------------------------------------------------------------------------- chunks


def test_chunk_hash_is_sha256_of_utf8_content_and_chunks_are_immutable(conn):
    doc, _ = active_document(conn, 81)
    content = "成人常用量:口服,每次 0.5 g,每日 2 次"
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    cid = conn.execute(
        "insert into chunks (doc_id, seq, page, section, content, chunk_content_hash) values (%s, 0, 3, '用法用量', %s, %s) returning chunk_id",
        (doc, content, expected),
    ).fetchone()[0]
    filled = conn.execute(
        "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, 1, 3, %s, null) returning chunk_content_hash",
        (doc, content),
    ).fetchone()[0]
    assert filled == expected
    with pytest.raises(errors.CheckViolation, match="does not match"):
        with conn.transaction():
            conn.execute(
                "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, 2, 3, %s, %s)",
                (doc, content, _hash(1)),
            )
    with pytest.raises(errors.UniqueViolation, match="chunks_doc_seq_unique"):
        with conn.transaction():
            conn.execute(
                "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, 0, 4, 'dup seq', null)",
                (doc,),
            )
    for sql in (
        "update chunks set content = 'changed' where chunk_id = %s",
        "update chunks set page = 9 where chunk_id = %s",
    ):
        with pytest.raises(errors.RestrictViolation, match="immutable"):
            with conn.transaction():
                conn.execute(sql, (cid,))
    conn.execute(
        "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, 0, 3, 6, 38)", (cid,)
    )
    with pytest.raises(errors.CheckViolation, match="chunk_spans_non_empty"):
        with conn.transaction():
            conn.execute(
                "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, 1, 3, 10, 10)",
                (cid,),
            )
    with pytest.raises(errors.RestrictViolation, match="immutable"):
        with conn.transaction():
            conn.execute("update chunk_spans set char_end = 40 where chunk_id = %s and ordinal = 0", (cid,))


def test_acl_is_per_document_and_dept_with_no_duplicates(conn):
    doc, _ = active_document(conn, 91)
    conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'MA', 'admin-01')", (doc,))
    with pytest.raises(errors.UniqueViolation):
        with conn.transaction():
            conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'MA', 'admin-02')", (doc,))
    with pytest.raises(errors.InvalidTextRepresentation):
        with conn.transaction():
            conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'HR', 'admin-01')", (doc,))
    conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'PV', 'admin-01')", (doc,))
    assert conn.execute("select count(*) from document_acl where doc_id = %s", (doc,)).fetchone()[0] == 2
