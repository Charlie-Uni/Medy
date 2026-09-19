"""Knowledge governance fact plane: source objects, ingestion jobs, documents, chunks, ACL, audit (M1-06, M1-07).

Entity names follow the design document 3.3 (`documents`, `chunks`, `document_acl`, `doc_audit`);
`source_objects`, `ingestion_jobs` and `chunk_spans` come from baseline 3.3, 4.2 and the probe SPEC
section 6. Every rule below is enforced by the database, not by application code:

- INV-DATA-02  one active version per family: partial unique index on documents(family_id).
- 3.4 / INV-DATA-05  active requires effective_from, a trusted parse and the ingestion job that produced
  it; effective_to must be after effective_from; only drafts may lack effective_from.
- INV-DATA-04  source objects and chunks are immutable once written; a document never changes its
  family, version, source object or chain position; documents can only be deleted while draft.
- Status moves draft -> active -> archived only. Every status change needs a session actor
  (`SET LOCAL medops.actor`) and writes a doc_audit row in the same transaction; doc_audit is append-only.
- chunk_content_hash is SHA-256 of the UTF-8 content, verified (or filled) by trigger.
- No `tsvector` and no `vector` column: DEC-001 / DEC-002 are open (baseline 3.8).

Revision ID: 0001
Revises: None
"""

from __future__ import annotations

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TYPES = """
create type dept as enum ('MA', 'PV', 'CO');
create type doc_type as enum ('label', 'protocol', 'sop', 'guideline');
create type doc_status as enum ('draft', 'active', 'archived');
create type parse_quality as enum ('pending', 'trusted', 'low_trust');
create type integrity_status as enum ('pending', 'verified', 'failed');
create type ingestion_status as enum ('queued', 'running', 'succeeded', 'failed');
create type acl_permission as enum ('read');
"""

TABLES = """
create table source_objects (
    source_object_id uuid primary key default gen_random_uuid(),
    source_hash      char(64) not null unique check (source_hash ~ '^[0-9a-f]{64}$'),
    storage_uri      text not null check (length(storage_uri) > 0),
    byte_size        bigint not null check (byte_size > 0),
    mime             text not null check (length(mime) > 0),
    integrity_status integrity_status not null default 'pending',
    last_verified_at timestamptz,
    created_by       text not null check (length(created_by) > 0),
    created_at       timestamptz not null default now()
);
comment on table source_objects is 'Immutable original files; source_hash is the global de-duplication key (baseline 3.3).';

create table ingestion_jobs (
    job_id                 uuid primary key default gen_random_uuid(),
    source_object_id       uuid not null references source_objects (source_object_id),
    doc_id                 uuid,
    status                 ingestion_status not null default 'queued',
    attempt                integer not null default 1 check (attempt >= 1),
    parser_version         text,
    extraction_params_hash char(64) check (extraction_params_hash ~ '^[0-9a-f]{64}$'),
    parse_quality          parse_quality not null default 'pending',
    quality_score          numeric(5, 4) check (quality_score is null or (quality_score >= 0 and quality_score <= 1)),
    failure_reason         text,
    created_at             timestamptz not null default now(),
    started_at             timestamptz,
    finished_at            timestamptz,
    constraint ingestion_jobs_failed_has_reason check (status <> 'failed' or failure_reason is not null),
    constraint ingestion_jobs_succeeded_has_quality check (status <> 'succeeded' or parse_quality <> 'pending'),
    constraint ingestion_jobs_job_source_unique unique (job_id, source_object_id)
);

create table documents (
    doc_id                  uuid primary key default gen_random_uuid(),
    family_id               uuid not null,
    title                   text not null check (length(title) > 0),
    doc_type                doc_type not null,
    version                 text not null check (length(version) > 0),
    status                  doc_status not null default 'draft',
    effective_from          date,
    effective_to            date,
    source_object_id        uuid not null references source_objects (source_object_id),
    active_ingestion_job_id uuid,
    parse_quality           parse_quality not null default 'pending',
    supersedes              uuid references documents (doc_id),
    owner_dept              dept not null,
    language                text check (language in ('zh-Hans', 'zh-Hant', 'en', 'mixed')),
    created_by              text not null check (length(created_by) > 0),
    created_at              timestamptz not null default now(),
    status_changed_by       text,
    status_changed_at       timestamptz,
    constraint documents_family_version_unique unique (family_id, version),
    constraint documents_supersedes_unique unique (supersedes),
    constraint documents_no_self_supersede check (supersedes is distinct from doc_id),
    constraint documents_effective_window check (effective_to is null or effective_from is null or effective_to > effective_from),
    constraint documents_non_draft_has_effective_from check (status = 'draft' or effective_from is not null),
    constraint documents_active_is_trusted check (status <> 'active' or parse_quality = 'trusted'),
    constraint documents_active_has_job check (status <> 'active' or active_ingestion_job_id is not null),
    constraint documents_job_matches_source foreign key (active_ingestion_job_id, source_object_id)
        references ingestion_jobs (job_id, source_object_id)
);
create unique index documents_one_active_per_family on documents (family_id) where status = 'active';
comment on index documents_one_active_per_family is 'INV-DATA-02: at most one active version per family_id.';

alter table ingestion_jobs add constraint ingestion_jobs_doc_fk foreign key (doc_id) references documents (doc_id);

create table chunks (
    chunk_id           uuid primary key default gen_random_uuid(),
    doc_id             uuid not null references documents (doc_id) on delete cascade,
    seq                integer not null check (seq >= 0),
    page               integer not null check (page >= 1),
    section            text,
    content            text not null check (length(content) > 0),
    chunk_content_hash char(64) not null check (chunk_content_hash ~ '^[0-9a-f]{64}$'),
    created_at         timestamptz not null default now(),
    constraint chunks_doc_seq_unique unique (doc_id, seq)
);

create table chunk_spans (
    chunk_id   uuid not null references chunks (chunk_id) on delete cascade,
    ordinal    integer not null check (ordinal >= 0),
    page       integer not null check (page >= 1),
    char_start integer not null check (char_start >= 0),
    char_end   integer not null,
    primary key (chunk_id, ordinal),
    constraint chunk_spans_non_empty check (char_end > char_start)
);
comment on table chunk_spans is 'Page-anchored character ranges of a chunk in normalised page text (SPEC section 6).';

create table document_acl (
    doc_id     uuid not null references documents (doc_id) on delete cascade,
    dept       dept not null,
    permission acl_permission not null default 'read',
    granted_by text not null check (length(granted_by) > 0),
    granted_at timestamptz not null default now(),
    primary key (doc_id, dept, permission)
);

create table doc_audit (
    id          bigint generated always as identity primary key,
    doc_id      uuid not null references documents (doc_id),
    action      text not null check (length(action) > 0),
    from_status doc_status,
    to_status   doc_status,
    actor       text not null check (length(actor) > 0),
    reason      text,
    details     jsonb,
    occurred_at timestamptz not null default now()
);
comment on table doc_audit is 'Append-only (INV-OBS-02); status changes are written by trigger with the session actor.';
"""

FUNCTIONS = """
create function medops_forbid_change() returns trigger language plpgsql as $$
begin
    raise exception '% on % is not allowed: % rows are immutable', tg_op, tg_table_name, tg_table_name
        using errcode = 'restrict_violation';
end $$;

create function medops_source_objects_immutable() returns trigger language plpgsql as $$
begin
    if new.source_hash is distinct from old.source_hash
       or new.storage_uri is distinct from old.storage_uri
       or new.byte_size is distinct from old.byte_size
       or new.mime is distinct from old.mime
       or new.created_by is distinct from old.created_by
       or new.created_at is distinct from old.created_at then
        raise exception 'source_objects identity columns are immutable (INV-DATA-04)' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;

create function medops_documents_guard() returns trigger language plpgsql as $$
declare
    job_quality parse_quality;
    job_status  ingestion_status;
    actor       text;
begin
    if tg_op = 'UPDATE' then
        if new.family_id is distinct from old.family_id
           or new.version is distinct from old.version
           or new.doc_type is distinct from old.doc_type
           or new.source_object_id is distinct from old.source_object_id
           or new.supersedes is distinct from old.supersedes
           or new.created_by is distinct from old.created_by
           or new.created_at is distinct from old.created_at then
            raise exception 'documents identity columns are immutable (INV-DATA-04)' using errcode = 'restrict_violation';
        end if;
        if new.status is distinct from old.status then
            if not ((old.status = 'draft' and new.status = 'active') or (old.status = 'active' and new.status = 'archived')) then
                raise exception 'illegal status transition % -> %', old.status, new.status using errcode = 'check_violation';
            end if;
            actor := nullif(current_setting('medops.actor', true), '');
            if actor is null then
                raise exception 'status change requires SET LOCAL medops.actor' using errcode = 'insufficient_privilege';
            end if;
            new.status_changed_by := actor;
            new.status_changed_at := now();
        end if;
    end if;
    if new.active_ingestion_job_id is not null then
        select parse_quality, status into job_quality, job_status from ingestion_jobs where job_id = new.active_ingestion_job_id;
        if job_status is distinct from 'succeeded' then
            raise exception 'active_ingestion_job_id must reference a succeeded job' using errcode = 'check_violation';
        end if;
        if job_quality is distinct from new.parse_quality then
            raise exception 'documents.parse_quality (%) must equal the active job parse_quality (%)', new.parse_quality, job_quality
                using errcode = 'check_violation';
        end if;
    end if;
    return new;
end $$;

create function medops_documents_audit() returns trigger language plpgsql as $$
begin
    insert into doc_audit (doc_id, action, from_status, to_status, actor, reason)
    values (new.doc_id, 'status_change', old.status, new.status, new.status_changed_by,
            nullif(current_setting('medops.reason', true), ''));
    return null;
end $$;

create function medops_documents_delete_guard() returns trigger language plpgsql as $$
begin
    if old.status <> 'draft' then
        raise exception 'only draft documents can be deleted; archive instead' using errcode = 'restrict_violation';
    end if;
    return old;
end $$;

create function medops_chunks_hash() returns trigger language plpgsql as $$
declare
    computed char(64);
begin
    computed := encode(sha256(convert_to(new.content, 'UTF8')), 'hex');
    if new.chunk_content_hash is null then
        new.chunk_content_hash := computed;
    elsif new.chunk_content_hash <> computed then
        raise exception 'chunk_content_hash does not match sha256(content)' using errcode = 'check_violation';
    end if;
    return new;
end $$;
"""

TRIGGERS = """
create trigger source_objects_immutable before update on source_objects
    for each row execute function medops_source_objects_immutable();
create trigger source_objects_no_delete before delete on source_objects
    for each row execute function medops_forbid_change();

create trigger documents_guard before insert or update on documents
    for each row execute function medops_documents_guard();
create trigger documents_audit after update of status on documents
    for each row when (old.status is distinct from new.status) execute function medops_documents_audit();
create trigger documents_delete_guard before delete on documents
    for each row execute function medops_documents_delete_guard();

create trigger chunks_hash before insert on chunks
    for each row execute function medops_chunks_hash();
create trigger chunks_immutable before update on chunks
    for each row execute function medops_forbid_change();
create trigger chunk_spans_immutable before update on chunk_spans
    for each row execute function medops_forbid_change();

create trigger doc_audit_append_only before update or delete on doc_audit
    for each row execute function medops_forbid_change();
"""

DROP_ALL = """
drop table if exists doc_audit;
drop table if exists document_acl;
drop table if exists chunk_spans;
drop table if exists chunks;
alter table if exists ingestion_jobs drop constraint if exists ingestion_jobs_doc_fk;
drop table if exists documents;
drop table if exists ingestion_jobs;
drop table if exists source_objects;
drop function if exists medops_chunks_hash();
drop function if exists medops_documents_delete_guard();
drop function if exists medops_documents_audit();
drop function if exists medops_documents_guard();
drop function if exists medops_source_objects_immutable();
drop function if exists medops_forbid_change();
drop type if exists acl_permission;
drop type if exists ingestion_status;
drop type if exists integrity_status;
drop type if exists parse_quality;
drop type if exists doc_status;
drop type if exists doc_type;
drop type if exists dept;
"""


def _execute_block(sql: str) -> None:
    for statement in _split(sql):
        op.execute(statement)


def _split(sql: str) -> list[str]:
    """Split on semicolons that end a statement, ignoring semicolons inside `$$ ... $$` bodies and
    inside single-quoted SQL string literals (a doubled quote toggles twice and stays inside)."""
    statements: list[str] = []
    buf: list[str] = []
    in_dollar = False
    in_quote = False
    i = 0
    while i < len(sql):
        two = sql[i : i + 2]
        if two == "$$" and not in_quote:
            in_dollar = not in_dollar
            buf.append(two)
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


def upgrade() -> None:
    _execute_block(TYPES)
    _execute_block(TABLES)
    _execute_block(FUNCTIONS)
    _execute_block(TRIGGERS)


def downgrade() -> None:
    _execute_block(DROP_ALL)
