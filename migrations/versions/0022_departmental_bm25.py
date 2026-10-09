"""Department-isolated production BM25 indexes (ADR-0002 revision 6).

The extension's corpus statistics are index-wide and do not obey row-level
security.  One table and BM25 index per department therefore prevent vocabulary
statistics from crossing the MA/PV/CO boundary.  Shared documents are copied to
each department corpus by the production builder and outbox consumer.  The A2
``chunk_lexical_tsv`` table remains intact as the rollback path.

Requires PostgreSQL 17 and the pinned pg_textsearch 1.5.1 binary in
``shared_preload_libraries`` before this migration runs.

Revision ID: 0022
Revises: 0021
"""

from __future__ import annotations

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

DEPARTMENTS = {"ma": "MA", "pv": "PV", "co": "CO"}
EXPECTED_EXTENSION_VERSION = "1.5.1"


def _table_sql(suffix: str, dept: str) -> str:
    table = f"chunk_lexical_bm25_{suffix}"
    index = f"{table}_idx"
    return f"""
create table {table} (
    chunk_id uuid primary key references chunks (chunk_id) on delete cascade,
    content  text not null check (content <> '')
);
comment on table {table} is
    'Production pg_textsearch BM25 corpus for {dept}; duplicated by document read ACL to isolate corpus statistics.';
create index {index} on {table} using bm25 (content)
    with (text_config = 'simple', k1 = 1.2, b = 0.75);
alter table {table} enable row level security;
alter table {table} force row level security;
create policy {table}_via_chunk on {table} for select to medops_app, medops_readonly
    using (medops_current_dept() = '{dept}'::dept
           and exists (select 1 from chunks c where c.chunk_id = {table}.chunk_id));
create policy {table}_admin_all on {table} for all to medops_admin_role using (true) with check (true);
grant select on {table} to medops_app, medops_readonly;
grant select, insert, update, delete on {table} to medops_admin_role;
"""


def upgrade() -> None:
    op.execute(
        f"""
do $$
begin
    if current_setting('server_version_num')::integer < 170000 then
        raise exception 'production BM25 requires PostgreSQL 17 or later';
    end if;
end $$;
create extension if not exists pg_textsearch;
do $$
declare installed text;
begin
    select extversion into installed from pg_extension where extname='pg_textsearch';
    if installed is distinct from '{EXPECTED_EXTENSION_VERSION}' then
        raise exception 'pg_textsearch version % does not equal pinned {EXPECTED_EXTENSION_VERSION}', installed;
    end if;
end $$;
"""
    )
    for suffix, dept in DEPARTMENTS.items():
        op.execute(_table_sql(suffix, dept))
    op.execute(
        """
create function medops_bm25_acl_revoke() returns trigger language plpgsql as $$
begin
    if old.permission = 'read' then
        if old.dept = 'MA'::dept then
            delete from chunk_lexical_bm25_ma i using chunks c
             where c.chunk_id=i.chunk_id and c.doc_id=old.doc_id;
        elsif old.dept = 'PV'::dept then
            delete from chunk_lexical_bm25_pv i using chunks c
             where c.chunk_id=i.chunk_id and c.doc_id=old.doc_id;
        elsif old.dept = 'CO'::dept then
            delete from chunk_lexical_bm25_co i using chunks c
             where c.chunk_id=i.chunk_id and c.doc_id=old.doc_id;
        end if;
    end if;
    return old;
end $$;
comment on function medops_bm25_acl_revoke() is
    'Remove revoked BM25 corpus rows in the ACL transaction; grants remain eventual through the outbox tokenizer.';
create trigger document_acl_bm25_revoke after delete on document_acl
    for each row execute function medops_bm25_acl_revoke();
"""
    )


def downgrade() -> None:
    op.execute("drop trigger if exists document_acl_bm25_revoke on document_acl")
    op.execute("drop function if exists medops_bm25_acl_revoke()")
    for suffix in reversed(tuple(DEPARTMENTS)):
        op.execute(f"drop table if exists chunk_lexical_bm25_{suffix}")
    # RESTRICT is intentional: an unregistered dependent index must block a
    # downgrade instead of being removed by surprise.
    op.execute("drop extension if exists pg_textsearch")
