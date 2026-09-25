"""Restricted, encrypted replay payloads (M3-07 / DEC-013, record 74 B; baseline 3.5, INV-OBS-03).

- `trace_payloads`: per trace and node, an envelope-encrypted blob (AES-256-GCM with a per-row DEK wrapped by a
  versioned KEK); the application role may only INSERT (written inside the request transaction), the restricted
  role reads and purges, the admin role sees only the access log.
- `payload_access_log`: append-only record of every read (principal pseudonym, purpose).
- `medops_restricted_role`: NOLOGIN group for the payload reader / retention job.

Revision ID: 0015
Revises: 0014
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

UP = """
do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'medops_restricted_role') then
        execute 'create role medops_restricted_role nologin nosuperuser nobypassrls nocreatedb nocreaterole noreplication inherit';
    end if;
end $$;
grant usage on schema public to medops_restricted_role;

create table trace_payloads (
    payload_id   uuid primary key,
    trace_id     text not null references traces (trace_id),
    node         text not null check (length(node) between 1 and 64),
    kind         text not null check (kind in ('input', 'evidence_snapshot', 'model_output')),
    ciphertext   bytea not null,
    nonce        bytea not null check (length(nonce) = 12),
    dek_wrapped  bytea not null,
    kek_version  text not null check (length(kek_version) between 1 and 64),
    created_at   timestamptz not null default now(),
    expires_at   timestamptz not null,
    constraint trace_payloads_one_per_kind unique (trace_id, node, kind)
);
comment on table trace_payloads is 'INV-OBS-03: replayable inputs / evidence / model outputs, envelope-encrypted, separate role, retention (DEC-013: 90 days, escalations +30 days after closing).';
create index trace_payloads_expiry on trace_payloads (expires_at);
create trigger trace_payloads_guard before update on trace_payloads for each row execute function medops_append_only();

create table payload_access_log (
    log_id      bigint generated always as identity primary key,
    trace_id    text not null,
    principal   text not null check (principal ~ '^[0-9a-f]{32,64}$'),
    purpose     text not null check (length(purpose) between 8 and 500),
    occurred_at timestamptz not null default now()
);
comment on table payload_access_log is 'Every read of a restricted payload: who, which trace, why (DEC-013).';
create index payload_access_log_trace on payload_access_log (trace_id, occurred_at desc);
create trigger payload_access_log_guard before update or delete on payload_access_log for each row execute function medops_append_only();

alter table trace_payloads enable row level security;
alter table trace_payloads force row level security;
alter table payload_access_log enable row level security;
alter table payload_access_log force row level security;

create policy trace_payloads_app_insert on trace_payloads for insert to medops_app with check (true);
create policy trace_payloads_restricted on trace_payloads for all to medops_restricted_role using (true) with check (true);
create policy payload_access_log_restricted_insert on payload_access_log for insert to medops_restricted_role with check (true);
create policy payload_access_log_read on payload_access_log for select to medops_restricted_role, medops_admin_role using (true);

grant insert on trace_payloads to medops_app;
grant select, delete on trace_payloads to medops_restricted_role;
grant select on traces, escalations to medops_restricted_role;
-- the retention rules read escalation state: FORCE RLS on traces / escalations needs an explicit read policy
create policy traces_restricted_read on traces for select to medops_restricted_role using (true);
create policy escalations_restricted_read on escalations for select to medops_restricted_role using (true);
grant insert, select on payload_access_log to medops_restricted_role;
grant select on payload_access_log to medops_admin_role;
"""

DOWN = """
drop policy if exists traces_restricted_read on traces;
drop policy if exists escalations_restricted_read on escalations;
drop table if exists payload_access_log;
drop table if exists trace_payloads;
revoke select on traces, escalations from medops_restricted_role;
revoke usage on schema public from medops_restricted_role;
-- the group role is cluster-wide and survives a downgrade like the roles of migration 0002
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
