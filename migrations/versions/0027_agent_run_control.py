"""Metadata-only Agent cancellation, leases and decision fences; not a recovery checkpoint.

Revision ID: 0027
Revises: 0026

No narrative, evidence, prompt, result or provider credentials are stored here.
The trusted application enforces principal ownership; RLS also enforces department.
"""

from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
create table agent_run_control (
    run_id uuid primary key,
    case_id uuid not null,
    task_id uuid not null,
    attempt_id uuid not null,
    principal text not null check (principal ~ '^[0-9a-f]{32,64}$'),
    dept dept not null,
    trace_id text not null check (trace_id ~ '^[0-9a-f]{32}$'),
    context_sha256 text not null check (context_sha256 ~ '^[0-9a-f]{64}$'),
    started_at timestamptz not null,
    expires_at timestamptz not null,
    decisions_consumed integer not null default 0 check (decisions_consumed between 0 and 8),
    lease_id uuid,
    lease_generation bigint not null default 0 check (lease_generation >= 0),
    lease_until timestamptz,
    cancelled_at timestamptz,
    check (expires_at = started_at + interval '125 seconds'),
    check ((lease_id is null) = (lease_until is null)),
    check (lease_until is null or lease_until <= expires_at)
);
comment on table agent_run_control is 'Internal PV Agent control metadata; acquiring a lease does not authorize recovery, new budget or completion.';
create function medops_agent_control_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'INSERT' then
        if new.decisions_consumed <> 0 or new.lease_generation <> 0 or new.lease_id is not null
           or new.cancelled_at is not null then
            raise exception 'agent control must start fresh' using errcode = 'restrict_violation';
        end if;
    elsif tg_op = 'DELETE' then
        raise exception 'agent control deletion requires a future retention contract' using errcode = 'restrict_violation';
    else
        if row(new.run_id,new.case_id,new.task_id,new.attempt_id,new.principal,new.dept,
               new.trace_id,new.context_sha256,new.started_at,new.expires_at)
           is distinct from
           row(old.run_id,old.case_id,old.task_id,old.attempt_id,old.principal,old.dept,
               old.trace_id,old.context_sha256,old.started_at,old.expires_at) then
            raise exception 'agent control binding is immutable' using errcode = 'restrict_violation';
        end if;
        if old.cancelled_at is not null then
            raise exception 'cancelled agent control is immutable' using errcode = 'restrict_violation';
        end if;
        if new.decisions_consumed < old.decisions_consumed or new.decisions_consumed > old.decisions_consumed + 1
           or new.lease_generation < old.lease_generation or new.lease_generation > old.lease_generation + 1 then
            raise exception 'agent control counters cannot reset or skip' using errcode = 'restrict_violation';
        end if;
    end if;
    return new;
end $$;
create trigger agent_control_guard before insert or update or delete on agent_run_control
    for each row execute function medops_agent_control_guard();
alter table agent_run_control enable row level security;
alter table agent_run_control force row level security;
create policy agent_control_app on agent_run_control for all to medops_app
    using (dept = medops_current_dept()) with check (dept = medops_current_dept());
create policy agent_control_admin_read on agent_run_control for select to medops_admin_role using (true);
grant select, insert, update on agent_run_control to medops_app;
grant select on agent_run_control to medops_admin_role;
""")


def downgrade() -> None:
    op.execute("drop table agent_run_control; drop function medops_agent_control_guard()")
