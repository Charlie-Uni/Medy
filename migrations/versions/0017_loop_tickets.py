"""M4-02 / M4-05 (record 80): rule-based attribution and knowledge-gap document tickets.

- `bad_cases.attributed_by` gains `rules`: Reflect's first pass is deterministic (record 74 C), a model or a human may
  follow.
- `document_requests`: the only thing the Loop may do with a knowledge gap is ask for a document (baseline 5.8: "knowledge
  gap 只能建补充文档工单，不能生成事实"). A ticket carries the question and a gap description, never content; the Loop
  role opens tickets, humans (admin role) accept / reject / fulfil them, and the opening fields are immutable.

Revision ID: 0017
Revises: 0016
"""

from __future__ import annotations

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

UP = r"""
alter table bad_cases drop constraint bad_cases_attributed_by_check;
alter table bad_cases add constraint bad_cases_attributed_by_check check (attributed_by in ('rules', 'model', 'human'));

create table document_requests (
    request_id uuid primary key default gen_random_uuid(),
    case_id uuid not null unique references bad_cases (case_id),
    dept dept not null,
    topic text not null check (length(topic) between 1 and 500),
    gap text not null check (length(gap) between 1 and 500),
    requested_by text not null,
    requested_at timestamptz not null default now(),
    status text not null default 'open' check (status in ('open', 'accepted', 'rejected', 'fulfilled')),
    handled_by text,
    handled_at timestamptz,
    note text check (note is null or length(note) <= 1000),
    document_id uuid references documents (doc_id)
);
comment on table document_requests is 'M4-05: knowledge-gap tickets opened by the Loop; question + gap description only, never generated content; humans (admin role) move the status and may link the document that closed the gap.';
create index document_requests_status_idx on document_requests (status, requested_at);

create function medops_document_request_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'document requests are never deleted' using errcode = 'restrict_violation';
    end if;
    if new.request_id is distinct from old.request_id or new.case_id is distinct from old.case_id
       or new.dept is distinct from old.dept or new.topic is distinct from old.topic or new.gap is distinct from old.gap
       or new.requested_by is distinct from old.requested_by or new.requested_at is distinct from old.requested_at then
        raise exception 'document request identity and content are immutable' using errcode = 'restrict_violation';
    end if;
    if not pg_has_role(current_user, 'medops_admin_role', 'member') then
        raise exception 'document requests are handled by the admin role only' using errcode = 'insufficient_privilege';
    end if;
    if old.status in ('rejected', 'fulfilled') and new.status <> old.status then
        raise exception 'a closed document request stays closed' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;
create trigger document_requests_guard before update or delete on document_requests
    for each row execute function medops_document_request_guard();

alter table document_requests enable row level security;
alter table document_requests force row level security;
create policy document_requests_loop on document_requests for all to medops_loop_role using (true) with check (true);
create policy document_requests_admin on document_requests for all to medops_admin_role using (true) with check (true);
grant select, insert on document_requests to medops_loop_role;
grant select, update on document_requests to medops_admin_role;
"""

DOWN = r"""
drop trigger if exists document_requests_guard on document_requests;
drop function if exists medops_document_request_guard();
drop table if exists document_requests;
alter table bad_cases drop constraint bad_cases_attributed_by_check;
alter table bad_cases add constraint bad_cases_attributed_by_check check (attributed_by in ('model', 'human'));
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
