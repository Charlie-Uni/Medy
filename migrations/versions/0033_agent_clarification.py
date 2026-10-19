"""Metadata-only clarification cases, batch ceilings and durable command reservations.

Revision ID: 0033
Revises: 0032

No business text is copied here. Questions/material remain in encrypted Agent journals.
Tombstones/reservations are retained; downgrade refuses retained cases or grants.
"""

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
create table agent_clarification_batches (
    batch_id uuid primary key,
    principal text not null,
    dept dept not null,
    authorization_sha256 text not null check (authorization_sha256 ~ '^[0-9a-f]{64}$'),
    case_ids uuid[] not null check (cardinality(case_ids) between 1 and 256),
    expires_at timestamptz not null,
    max_executions bigint not null check (max_executions > 0),
    cost_limit_microusd bigint not null check (cost_limit_microusd > 0)
);
create table agent_clarification_cases (
    case_id uuid primary key,
    principal text not null,
    dept dept not null,
    initial_run_id uuid not null unique,
    initial_context_sha256 text not null check (initial_context_sha256 ~ '^[0-9a-f]{64}$'),
    policy_sha256 text not null check (policy_sha256 ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz not null,
    max_continuations bigint not null check (max_continuations > 0),
    cost_limit_microusd bigint not null check (cost_limit_microusd > 0),
    current_run_id uuid not null unique,
    revision bigint not null default 1 check (revision > 0),
    deleted_at timestamptz
);
create table agent_clarification_executions (
    run_id uuid primary key,
    case_id uuid not null references agent_clarification_cases(case_id),
    principal text not null,
    dept dept not null,
    command_id uuid unique,
    batch_id uuid references agent_clarification_batches(batch_id),
    source_run_id uuid unique,
    request_sha256 text check (request_sha256 ~ '^[0-9a-f]{64}$'),
    context_sha256 text not null check (context_sha256 ~ '^[0-9a-f]{64}$'),
    ordinal bigint not null check (ordinal >= 0),
    accounted_cost_microusd bigint not null check (accounted_cost_microusd >= 0),
    known_cost_microusd bigint not null check (known_cost_microusd >= 0 and known_cost_microusd <= accounted_cost_microusd),
    held_cost_microusd bigint not null check (held_cost_microusd >= 0),
    settled boolean not null,
    unique(case_id, ordinal),
    check ((ordinal = 0) = (command_id is null)),
    check ((ordinal = 0) = (batch_id is null)),
    check ((ordinal = 0) = (source_run_id is null)),
    check ((ordinal = 0) = (request_sha256 is null)),
    check (not settled or held_cost_microusd = 0)
);
create index agent_clarification_batch_spend on agent_clarification_executions(batch_id);
create function medops_clarification_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' or tg_table_name = 'agent_clarification_batches' then
        raise exception 'retained clarification metadata is immutable' using errcode = 'restrict_violation';
    elsif tg_table_name = 'agent_clarification_cases' then
        if row(new.case_id,new.principal,new.dept,new.initial_run_id,new.initial_context_sha256,
               new.policy_sha256,new.expires_at,new.max_continuations,new.cost_limit_microusd)
           is distinct from
           row(old.case_id,old.principal,old.dept,old.initial_run_id,old.initial_context_sha256,
               old.policy_sha256,old.expires_at,old.max_continuations,old.cost_limit_microusd)
           or old.deleted_at is not null or new.revision <> old.revision + 1 then
            raise exception 'clarification case binding or revision invalid' using errcode = 'restrict_violation';
        end if;
    else
        if row(new.run_id,new.case_id,new.principal,new.dept,new.command_id,new.batch_id,new.source_run_id,
               new.request_sha256,new.context_sha256,new.ordinal)
           is distinct from
           row(old.run_id,old.case_id,old.principal,old.dept,old.command_id,old.batch_id,old.source_run_id,
               old.request_sha256,old.context_sha256,old.ordinal)
           or old.settled or not new.settled or new.held_cost_microusd <> 0
           or new.known_cost_microusd < old.known_cost_microusd
           or new.accounted_cost_microusd < old.accounted_cost_microusd then
            raise exception 'clarification allocation cannot reset' using errcode = 'restrict_violation';
        end if;
    end if;
    return new;
end $$;
""")
    for table in ("agent_clarification_batches", "agent_clarification_cases", "agent_clarification_executions"):
        op.execute(f"""
create trigger clarification_guard before update or delete on {table}
    for each row execute function medops_clarification_guard();
alter table {table} enable row level security;
alter table {table} force row level security;
create policy clarification_app on {table} for all to medops_app
    using (dept = medops_current_dept()) with check (dept = medops_current_dept());
create policy clarification_admin_read on {table} for select to medops_admin_role using (true);
grant select, insert, update on {table} to medops_app;
grant select on {table} to medops_admin_role;
""")


def downgrade() -> None:
    op.execute("""
do $$ begin
    if exists(select 1 from agent_clarification_cases) or exists(select 1 from agent_clarification_batches) then
        raise exception 'retained clarification metadata prevents downgrade' using errcode = 'restrict_violation';
    end if;
end $$;
drop table agent_clarification_executions;
drop table agent_clarification_cases;
drop table agent_clarification_batches;
drop function medops_clarification_guard();
""")
