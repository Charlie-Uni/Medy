"""Policy candidates, approvals and the released pointer (M3-03 / DEC-012, record 74; baseline 4.2
`policies/policy_releases`, INV-AUTH-05, INV-HAR-06), plus the outbox event for ACL changes.

- `policies`: one row per candidate diff (prompt / rule / skill / retrieval_params) with its lifecycle
  candidate -> approved | rejected -> released -> rolled_back; the decision (four-eyes) is recorded on the row.
- `policy_releases`: append-only log of release / rollback actions with the canary percentage and the previous pointer.
- `released_policies`: the pointer production reads — at most one released policy per (kind, name).
- `medops_loop_role`: NOLOGIN group that may only insert candidates and read policies (M4-04 proves it).
- outbox `document_acl_changed`: ACL grants / revokes invalidate the retrieval cache like status changes.

Revision ID: 0014
Revises: 0013
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

UP = """
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'medops_loop_role') then
        execute 'create role medops_loop_role nologin nosuperuser nobypassrls nocreatedb nocreaterole noreplication inherit';
    end if;
end $$;
grant usage on schema public to medops_loop_role;

alter table outbox_events drop constraint outbox_events_event_type_check;
alter table outbox_events add constraint outbox_events_event_type_check
    check (event_type in ('document_activated', 'document_archived', 'document_withdrawn', 'document_acl_changed'));

create table policies (
    policy_id        uuid primary key,
    kind             text not null check (kind in ('prompt', 'rule', 'skill', 'retrieval_params')),
    name             text not null check (name ~ '^[a-z][a-z0-9_.-]{1,63}$'),
    version          text not null check (length(version) between 1 and 64),
    diff             jsonb not null,
    evidence         jsonb not null default '{}'::jsonb,
    status           text not null default 'candidate'
                     check (status in ('candidate', 'approved', 'rejected', 'released', 'rolled_back')),
    created_by       text not null check (length(created_by) > 0),
    created_at       timestamptz not null default now(),
    decided_by       text,
    decided_at       timestamptz,
    decision_reason  text,
    constraint policies_kind_name_version unique (kind, name, version),
    constraint policies_decision_complete check (
        (status = 'candidate' and decided_by is null and decided_at is null)
        or (status <> 'candidate' and decided_by is not null and decided_at is not null)
    )
);
comment on table policies is 'M3-03 / M4: candidate diffs and their lifecycle; the loop role inserts candidates only, decisions are recorded with the approver pseudonym.';
create index policies_status_created on policies (status, created_at desc);

create table policy_releases (
    release_id        uuid primary key,
    policy_id         uuid not null references policies (policy_id),
    action            text not null check (action in ('release', 'rollback')),
    canary_percent    integer check (canary_percent between 0 and 100),
    previous_policy   uuid references policies (policy_id),
    actor             text not null check (length(actor) > 0),
    reason            text,
    occurred_at       timestamptz not null default now()
);
comment on table policy_releases is 'Append-only release / rollback log (baseline 4.2 policy_releases).';
create index policy_releases_policy on policy_releases (policy_id, occurred_at desc);
create trigger policy_releases_guard before update or delete on policy_releases for each row execute function medops_append_only();

create table released_policies (
    kind        text not null,
    name        text not null,
    policy_id   uuid not null references policies (policy_id),
    updated_at  timestamptz not null default now(),
    updated_by  text not null,
    primary key (kind, name)
);
comment on table released_policies is 'The released pointer production reads (INV-HAR-06); switched atomically by release / rollback.';

alter table policies enable row level security;
alter table policies force row level security;
alter table policy_releases enable row level security;
alter table policy_releases force row level security;
alter table released_policies enable row level security;
alter table released_policies force row level security;

create policy policies_admin on policies for all to medops_admin_role using (true) with check (true);
create policy policies_loop_insert on policies for insert to medops_loop_role with check (status = 'candidate');
create policy policies_loop_select on policies for select to medops_loop_role using (true);
create policy policies_read on policies for select to medops_app, medops_readonly using (true);
create policy policy_releases_admin on policy_releases for all to medops_admin_role using (true) with check (true);
create policy policy_releases_read on policy_releases for select to medops_app, medops_readonly, medops_loop_role using (true);
create policy released_policies_admin on released_policies for all to medops_admin_role using (true) with check (true);
create policy released_policies_read on released_policies for select to medops_app, medops_readonly, medops_loop_role using (true);

grant select, insert, update on policies to medops_admin_role;
grant select, insert on policy_releases to medops_admin_role;
grant select, insert, update, delete on released_policies to medops_admin_role;
grant select, insert on policies to medops_loop_role;
grant select on policy_releases, released_policies to medops_loop_role;
grant select on policies, policy_releases, released_policies to medops_app, medops_readonly;

-- admin routes run on the admin role and record their own idempotency receipts (M3-03)
create policy idempotency_keys_admin_insert on idempotency_keys for insert to medops_admin_role with check (true);
grant insert on idempotency_keys to medops_admin_role;
"""

DOWN = """
drop policy if exists idempotency_keys_admin_insert on idempotency_keys;
revoke insert on idempotency_keys from medops_admin_role;
drop table if exists released_policies;
drop table if exists policy_releases;
drop table if exists policies;
alter table outbox_events drop constraint outbox_events_event_type_check;
alter table outbox_events add constraint outbox_events_event_type_check
    check (event_type in ('document_activated', 'document_archived', 'document_withdrawn'));
revoke usage on schema public from medops_loop_role;
-- the group role is cluster-wide and survives a downgrade like the roles of migration 0002
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
