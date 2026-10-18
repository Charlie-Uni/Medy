"""Seal Agent control after an atomic encrypted terminal commit.

Revision ID: 0030
Revises: 0029
Only lifecycle metadata; no narratives, new role grants or existing task enums.
"""

from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
alter table agent_run_control add column terminal_ref uuid;
alter table agent_run_control add column terminal_at timestamptz;
alter table agent_run_control add column terminal_status text;
alter table agent_run_control add constraint agent_terminal_metadata check (
    (terminal_ref is null and terminal_at is null and terminal_status is null) or
    (terminal_ref is not null and terminal_at is not null and terminal_at >= started_at
     and terminal_status is not null and terminal_status in ('completed','awaiting_clarification','escalated','failed','cancelled'))
);
create or replace function medops_agent_control_guard() returns trigger language plpgsql as $$
begin
    if tg_op='INSERT' then
        if new.decisions_consumed<>0 or new.lease_generation<>0 or new.lease_id is not null
           or new.cancelled_at is not null or new.terminal_ref is not null then
            raise exception 'agent control must start fresh' using errcode='restrict_violation';
        end if;
    elsif tg_op='DELETE' then
        raise exception 'agent control deletion requires a future retention contract' using errcode='restrict_violation';
    else
        if row(new.run_id,new.case_id,new.task_id,new.attempt_id,new.principal,new.dept,
               new.trace_id,new.context_sha256,new.started_at,new.expires_at)
           is distinct from row(old.run_id,old.case_id,old.task_id,old.attempt_id,old.principal,old.dept,
               old.trace_id,old.context_sha256,old.started_at,old.expires_at) then
            raise exception 'agent control binding is immutable' using errcode='restrict_violation';
        end if;
        if old.terminal_ref is not null then
            raise exception 'terminal agent control is immutable' using errcode='restrict_violation';
        end if;
        if new.terminal_ref is not null then
            if new.terminal_status not in ('failed','cancelled') and (
                new.cancelled_at is not null or clock_timestamp()>=new.expires_at
                or new.lease_until is null or clock_timestamp()>=new.lease_until
                or not exists(select 1 from agent_runtime_heads h where h.run_id=new.run_id
                    and h.budget_deadline>clock_timestamp())
            ) then
                raise exception 'terminal publication requires the original live budget' using errcode='restrict_violation';
            end if;
            if row(new.decisions_consumed,new.lease_id,new.lease_generation,new.lease_until,new.cancelled_at)
               is distinct from row(old.decisions_consumed,old.lease_id,old.lease_generation,old.lease_until,old.cancelled_at)
               or not exists(select 1 from agent_runtime_events e where e.event_id=new.terminal_ref
                 and e.run_id=new.run_id and e.principal=new.principal and e.dept=new.dept
                 and e.lease_id=new.lease_id and e.lease_generation=new.lease_generation
                 and e.kind='late_stop') then
                raise exception 'terminal must bind an immutable owned event' using errcode='restrict_violation';
            end if;
        elsif old.cancelled_at is not null then
            raise exception 'cancelled agent control is immutable' using errcode='restrict_violation';
        end if;
        if new.decisions_consumed<old.decisions_consumed or new.decisions_consumed>old.decisions_consumed+1
           or new.lease_generation<old.lease_generation or new.lease_generation>old.lease_generation+1 then
            raise exception 'agent control counters cannot reset or skip' using errcode='restrict_violation';
        end if;
    end if;
    return new;
end $$;
create function medops_agent_terminal_write_guard() returns trigger language plpgsql as $$
begin
    if exists(select 1 from agent_run_control c where c.run_id=new.run_id and c.terminal_ref is not null) then
        if tg_table_name='agent_runtime_events' then
            if new.kind in ('call_settled','late_stop') then
                return new;
            end if;
        end if;
        raise exception 'terminal agent cannot advance or admit a new call' using errcode='restrict_violation';
    end if;
    return new;
end $$;
create trigger agent_terminal_head_guard before insert or update on agent_runtime_heads
    for each row execute function medops_agent_terminal_write_guard();
create trigger agent_terminal_event_guard before insert on agent_runtime_events
    for each row execute function medops_agent_terminal_write_guard();
""")


def downgrade() -> None:
    op.execute("""
do $$ begin
    if exists(select 1 from agent_run_control where terminal_ref is not null) then
        raise exception 'cannot downgrade sealed agent executions' using errcode='restrict_violation';
    end if;
end $$;
drop trigger agent_terminal_head_guard on agent_runtime_heads;
drop trigger agent_terminal_event_guard on agent_runtime_events;
drop function medops_agent_terminal_write_guard();
""")
    op.execute("""
create or replace function medops_agent_control_guard() returns trigger language plpgsql as $$
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
""")
    op.execute(
        "alter table agent_run_control drop constraint agent_terminal_metadata, drop column terminal_ref, drop column terminal_at, drop column terminal_status"
    )
