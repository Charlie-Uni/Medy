"""Terminal `withdrawn` status for drafts (owner decision 2026-09-17, record 20 question 2).

A mis-ingested draft carries an `ingest` audit row; audit is append-only and its foreign key does not
cascade, so the draft can neither be deleted nor archived (draft -> archived is illegal). `withdrawn`
is a terminal state only a draft may enter; the change needs `SET LOCAL medops.actor`, is audited by
the existing trigger, withdrawn documents are never visible to app/readonly roles, and like drafts they
need no effective_from (constraint widened).

Downgrade restores the previous guard and policy definitions. PostgreSQL cannot drop an enum value,
so the label stays in the type; the downgrade refuses while any withdrawn row exists. The full
round trip is still clean because revision 0001 drops the whole type.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

GUARD_V2 = """
create or replace function medops_documents_guard() returns trigger language plpgsql as $$
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
        if old.status = 'withdrawn' and (new.status is distinct from old.status or row(new.*) is distinct from row(old.*)) then
            raise exception 'withdrawn documents are terminal and read-only' using errcode = 'restrict_violation';
        end if;
        if new.status is distinct from old.status then
            if not ((old.status = 'draft' and new.status = 'active')
                    or (old.status = 'active' and new.status = 'archived')
                    or (old.status = 'draft' and new.status = 'withdrawn')) then
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
end $$
"""

GUARD_V1 = """
create or replace function medops_documents_guard() returns trigger language plpgsql as $$
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
end $$
"""

POLICY_V2 = """
create policy documents_dept_read on documents for select to medops_app, medops_readonly
    using (status in ('active', 'archived') and exists (
        select 1 from document_acl a
        where a.doc_id = documents.doc_id and a.permission = 'read' and a.dept = medops_current_dept()))
"""

POLICY_V1 = """
create policy documents_dept_read on documents for select to medops_app, medops_readonly
    using (status <> 'draft' and exists (
        select 1 from document_acl a
        where a.doc_id = documents.doc_id and a.permission = 'read' and a.dept = medops_current_dept()))
"""


def upgrade() -> None:
    # A new enum value cannot be referenced in the transaction that adds it (the CHECK below does), so the
    # ADD VALUE runs in its own autocommit block, as Alembic recommends for enum extensions.
    with op.get_context().autocommit_block():
        op.execute("alter type doc_status add value if not exists 'withdrawn'")
    op.execute(GUARD_V2)
    op.execute("drop policy if exists documents_dept_read on documents")
    op.execute(POLICY_V2)
    op.execute("alter table documents drop constraint documents_non_draft_has_effective_from")
    op.execute(
        "alter table documents add constraint documents_non_draft_has_effective_from "
        "check (status in ('draft', 'withdrawn') or effective_from is not null)"
    )


def downgrade() -> None:
    op.execute(
        "do $$ begin if exists (select 1 from documents where status = 'withdrawn') then "
        "raise exception 'cannot downgrade: withdrawn documents exist'; end if; end $$"
    )
    op.execute("alter table documents drop constraint documents_non_draft_has_effective_from")
    op.execute(
        "alter table documents add constraint documents_non_draft_has_effective_from "
        "check (status = 'draft' or effective_from is not null)"
    )
    op.execute("drop policy if exists documents_dept_read on documents")
    op.execute(POLICY_V1)
    op.execute(GUARD_V1)
