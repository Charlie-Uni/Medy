"""Database roles, grants and row-level security for the knowledge tables (M1-08; baseline 3.7, INV-AUTH-01/02/04/05).

Roles (cluster-wide, NOLOGIN, created only if missing; never dropped by downgrade):
- medops_app         API and worker: read non-draft documents of the caller's department under RLS.
- medops_readonly    MCP server: same visibility, no write privilege at all (INV-AUTH-04 proven by grants).
- medops_admin_role  document management and review: full visibility and writes, still NOSUPERUSER /
                     NOBYPASSRLS so triggers, constraints and audit apply. Not a table owner.
LOGIN users are created per environment by `python -m medops.infrastructure.db.login_users` and
inherit one of these groups; passwords never enter a revision.

Identity comes from the transaction: the server sets `SET LOCAL medops.dept = '<MA|PV|CO>'` from the
verified token. `medops_current_dept()` returns NULL when unset, so every policy evaluates to false:
default deny. Drafts are never visible to app/readonly. All seven tables have RLS enabled AND forced.
Status and effective-time filtering for evidence stays in the queries (baseline 3.4); RLS is the
department boundary that no query can cross.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

ROLES = ("medops_app", "medops_readonly", "medops_admin_role")
TABLES = ("source_objects", "ingestion_jobs", "documents", "chunks", "chunk_spans", "document_acl", "doc_audit")

CREATE_ROLES = """
do $$
declare r text;
begin
    foreach r in array array['medops_app', 'medops_readonly', 'medops_admin_role'] loop
        if not exists (select 1 from pg_roles where rolname = r) then
            execute format('create role %I nologin nosuperuser nobypassrls nocreatedb nocreaterole noreplication inherit', r);
        end if;
    end loop;
end $$;
"""

IDENTITY = """
create function medops_current_dept() returns dept language sql stable as $$
    select nullif(current_setting('medops.dept', true), '')::dept
$$;
comment on function medops_current_dept() is 'Department injected per transaction with SET LOCAL medops.dept; NULL means no identity, policies then deny.';
"""

GRANTS = """
grant usage on schema public to medops_app, medops_readonly, medops_admin_role;
grant select on documents, chunks, chunk_spans, document_acl, source_objects to medops_app, medops_readonly;
grant select, insert, update on source_objects, ingestion_jobs, documents, document_acl to medops_admin_role;
grant select, insert on chunks, chunk_spans, doc_audit to medops_admin_role;
grant delete on documents, document_acl to medops_admin_role;
grant usage, select on all sequences in schema public to medops_admin_role;
"""

RLS = """
alter table source_objects enable row level security;
alter table source_objects force row level security;
alter table ingestion_jobs enable row level security;
alter table ingestion_jobs force row level security;
alter table documents enable row level security;
alter table documents force row level security;
alter table chunks enable row level security;
alter table chunks force row level security;
alter table chunk_spans enable row level security;
alter table chunk_spans force row level security;
alter table document_acl enable row level security;
alter table document_acl force row level security;
alter table doc_audit enable row level security;
alter table doc_audit force row level security;

create policy document_acl_own_dept on document_acl for select to medops_app, medops_readonly
    using (dept = medops_current_dept());
create policy documents_dept_read on documents for select to medops_app, medops_readonly
    using (status <> 'draft' and exists (
        select 1 from document_acl a
        where a.doc_id = documents.doc_id and a.permission = 'read' and a.dept = medops_current_dept()));
create policy chunks_via_document on chunks for select to medops_app, medops_readonly
    using (exists (select 1 from documents d where d.doc_id = chunks.doc_id));
create policy chunk_spans_via_chunk on chunk_spans for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = chunk_spans.chunk_id));
create policy source_objects_via_document on source_objects for select to medops_app, medops_readonly
    using (exists (select 1 from documents d where d.source_object_id = source_objects.source_object_id));

create policy source_objects_admin_all on source_objects for all to medops_admin_role using (true) with check (true);
create policy ingestion_jobs_admin_all on ingestion_jobs for all to medops_admin_role using (true) with check (true);
create policy documents_admin_all on documents for all to medops_admin_role using (true) with check (true);
create policy chunks_admin_all on chunks for all to medops_admin_role using (true) with check (true);
create policy chunk_spans_admin_all on chunk_spans for all to medops_admin_role using (true) with check (true);
create policy document_acl_admin_all on document_acl for all to medops_admin_role using (true) with check (true);
create policy doc_audit_admin_all on doc_audit for all to medops_admin_role using (true) with check (true);
"""

DROP = """
drop policy if exists doc_audit_admin_all on doc_audit;
drop policy if exists document_acl_admin_all on document_acl;
drop policy if exists chunk_spans_admin_all on chunk_spans;
drop policy if exists chunks_admin_all on chunks;
drop policy if exists documents_admin_all on documents;
drop policy if exists ingestion_jobs_admin_all on ingestion_jobs;
drop policy if exists source_objects_admin_all on source_objects;
drop policy if exists source_objects_via_document on source_objects;
drop policy if exists chunk_spans_via_chunk on chunk_spans;
drop policy if exists chunks_via_document on chunks;
drop policy if exists documents_dept_read on documents;
drop policy if exists document_acl_own_dept on document_acl;
alter table doc_audit no force row level security;
alter table doc_audit disable row level security;
alter table document_acl no force row level security;
alter table document_acl disable row level security;
alter table chunk_spans no force row level security;
alter table chunk_spans disable row level security;
alter table chunks no force row level security;
alter table chunks disable row level security;
alter table documents no force row level security;
alter table documents disable row level security;
alter table ingestion_jobs no force row level security;
alter table ingestion_jobs disable row level security;
alter table source_objects no force row level security;
alter table source_objects disable row level security;
revoke all on all tables in schema public from medops_app, medops_readonly, medops_admin_role;
revoke all on all sequences in schema public from medops_app, medops_readonly, medops_admin_role;
revoke usage on schema public from medops_app, medops_readonly, medops_admin_role;
drop function if exists medops_current_dept();
"""


def _split(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    in_dollar = in_quote = False
    i = 0
    while i < len(sql):
        if sql[i : i + 2] == "$$" and not in_quote:
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        ch = sql[i]
        if ch == "'" and not in_dollar:
            in_quote = not in_quote
        if ch == ";" and not in_dollar and not in_quote:
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _run(sql: str) -> None:
    for statement in _split(sql):
        op.execute(statement)


def upgrade() -> None:
    _run(CREATE_ROLES)
    _run(IDENTITY)
    _run(GRANTS)
    _run(RLS)


def downgrade() -> None:
    # Roles are cluster-wide and may be referenced by login users or other databases; they are left in place.
    _run(DROP)
