"""Vector stage (M1-16; ADR-0007 / DEC-002): pgvector extension, per-version chunk embeddings and the
embedding index metadata.

`chunk_embeddings` holds one 1024-dimensional, L2-normalised dense vector per chunk and embedding version
(primary key `(chunk_id, embedding_version)`), indexed with HNSW over cosine distance. The dimension is fixed
here because ADR-0007 fixed the model (`BAAI/bge-m3`); a future model with another dimension gets a new
column/table and index by a new revision, never an in-place change (baseline 3.8). `embedding_index_meta`
records, per embedding version, the model id, pinned revision, dimension, normalisation, truncation length
and framework the vectors were produced with; a query configuration that differs is refused by the adapter.

Access mirrors the lexical index tables: FORCE RLS, ordinary roles read a row only when the underlying chunk
is visible to them (documents policy chain), the admin role maintains the rows. The extension is created if
missing and deliberately NOT dropped on downgrade (it may pre-exist in a shared database).

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

EMBEDDING_DIMENSION = 1024

UP = f"""
create extension if not exists vector;

create table embedding_index_meta (
    embedding_version text primary key,
    model_id          text not null check (length(model_id) > 0),
    model_revision    text not null check (length(model_revision) > 0),
    dimension         integer not null check (dimension = {EMBEDDING_DIMENSION}),
    normalization     text not null check (length(normalization) > 0),
    max_seq_length    integer not null check (max_seq_length > 0),
    framework         text not null check (length(framework) > 0),
    chunk_count       integer not null check (chunk_count >= 0),
    built_by          text not null check (length(built_by) > 0),
    built_at          timestamptz not null default now()
);
comment on table embedding_index_meta is 'ADR-0007: what each embedding version was produced with; query-side configuration must match exactly.';

create table chunk_embeddings (
    chunk_id          uuid not null references chunks (chunk_id) on delete cascade,
    embedding_version text not null references embedding_index_meta (embedding_version),
    embedding         vector({EMBEDDING_DIMENSION}) not null,
    created_at        timestamptz not null default now(),
    primary key (chunk_id, embedding_version)
);
comment on table chunk_embeddings is 'M1-16 dense vectors per chunk and embedding version; L2-normalised, cosine distance (ADR-0007).';
create index chunk_embeddings_hnsw_cosine on chunk_embeddings using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

alter table embedding_index_meta enable row level security;
alter table embedding_index_meta force row level security;
create policy embedding_index_meta_read on embedding_index_meta for select to medops_app, medops_readonly using (true);
create policy embedding_index_meta_admin_all on embedding_index_meta for all to medops_admin_role using (true) with check (true);
grant select on embedding_index_meta to medops_app, medops_readonly;
grant select, insert, update, delete on embedding_index_meta to medops_admin_role;

alter table chunk_embeddings enable row level security;
alter table chunk_embeddings force row level security;
create policy chunk_embeddings_via_chunk on chunk_embeddings for select to medops_app, medops_readonly
    using (exists (select 1 from chunks c where c.chunk_id = chunk_embeddings.chunk_id));
create policy chunk_embeddings_admin_all on chunk_embeddings for all to medops_admin_role using (true) with check (true);
grant select on chunk_embeddings to medops_app, medops_readonly;
grant select, insert, update, delete on chunk_embeddings to medops_admin_role;
"""

DOWN = """
drop table if exists chunk_embeddings;
drop table if exists embedding_index_meta;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
