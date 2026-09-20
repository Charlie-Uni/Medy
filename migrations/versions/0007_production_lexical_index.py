"""Production lexical index (M1-14; DEC-001 final judgement in ADR-0002: candidate A2 = PostgreSQL `simple`
full-text search over application-side jieba tokens with the pinned English stopword list).

`lexical_index_meta` records, per index name, the retriever/tokenizer/dictionary/normalisation versions an
index was built with (the same table the DEC-001 experiments created ad hoc; created here idempotently so a
development database that already holds it upgrades cleanly). `chunk_lexical_tsv` is the production
`chunk_id -> tsvector` table with a GIN index. Both are FORCE RLS: ordinary roles read a row only when the
underlying chunk is visible to them; the admin role maintains the rows. Candidate B/C tables remain
experiment-scoped and are not part of any migration.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

TABLE = "chunk_lexical_tsv"
META = "lexical_index_meta"

UP = f"""
create table if not exists {META} (
    index_name            text primary key,
    retriever_version     text not null,
    tokenizer_version     text not null,
    dictionary_version    text not null,
    normalization_version text not null,
    chunk_count           integer not null check (chunk_count >= 0),
    built_by              text not null,
    built_at              timestamptz not null default now()
);
comment on table {META} is 'Versions each lexical index was BUILT with (baseline 3.6): a query configuration that differs is refused.';
alter table {META} enable row level security;
alter table {META} force row level security;
drop policy if exists {META}_read on {META};
create policy {META}_read on {META} for select to medops_app, medops_readonly using (true);
drop policy if exists {META}_admin_all on {META};
create policy {META}_admin_all on {META} for all to medops_admin_role using (true) with check (true);
grant select on {META} to medops_app, medops_readonly;
grant select, insert, update, delete on {META} to medops_admin_role;

create table {TABLE} (
    chunk_id uuid primary key references chunks (chunk_id) on delete cascade,
    tsv      tsvector not null
);
comment on table {TABLE} is 'M1-14 production lexical index: position-preserving tsvector of application-side tokens (candidate A2).';
create index {TABLE}_tsv_gin on {TABLE} using gin (tsv);
alter table {TABLE} enable row level security;
alter table {TABLE} force row level security;
create policy {TABLE}_via_chunk on {TABLE} for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = {TABLE}.chunk_id));
create policy {TABLE}_admin_all on {TABLE} for all to medops_admin_role using (true) with check (true);
grant select on {TABLE} to medops_app, medops_readonly;
grant select, insert, update, delete on {TABLE} to medops_admin_role;
"""

DOWN = f"""
drop table if exists {TABLE};
drop table if exists {META};
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
