"""Encrypted Agent runtime heads and append-only write-ahead/receipt events.

Revision ID: 0029
Revises: 0028
No existing table, identity grant or published policy is changed.
"""

from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
create table agent_runtime_heads (
    run_id uuid primary key references agent_run_control(run_id),
    principal text not null,
    dept dept not null,
    context_sha256 text not null check (context_sha256 ~ '^[0-9a-f]{64}$'),
    revision bigint not null check (revision >= 1),
    lease_id uuid not null,
    lease_generation bigint not null check (lease_generation >= 1),
    budget_state jsonb not null check (octet_length(budget_state::text) <= 2097152),
    budget_deadline timestamptz not null,
    ciphertext bytea not null check (octet_length(ciphertext) <= 20971536),
    nonce bytea not null check (octet_length(nonce)=12),
    dek_wrapped bytea not null,
    kek_version text not null,
    retained_until timestamptz not null,
    updated_at timestamptz not null default clock_timestamp()
);
create table agent_runtime_events (
    event_id uuid primary key,
    run_id uuid not null references agent_runtime_heads(run_id) on delete cascade,
    principal text not null,
    dept dept not null,
    lease_id uuid not null,
    lease_generation bigint not null check (lease_generation >= 1),
    kind text not null check (kind in ('call_admitted','call_settled','tool_committed','checkpoint','late_stop')),
    item_id uuid not null,
    ciphertext bytea not null check (octet_length(ciphertext) <= 20971536),
    nonce bytea not null check (octet_length(nonce)=12),
    dek_wrapped bytea not null,
    kek_version text not null,
    created_at timestamptz not null default clock_timestamp(),
    retained_until timestamptz not null,
    unique (run_id,kind,item_id)
);
create index agent_runtime_events_run on agent_runtime_events(run_id,created_at,event_id);
create index agent_runtime_heads_retention on agent_runtime_heads(retained_until);
comment on table agent_runtime_heads is 'Internal encrypted Agent recovery head. Budget metadata is not authorization. Revision and lease must be fenced before any provider call.';
comment on table agent_runtime_events is 'Encrypted append-only admissions, receipts and tool/checkpoint audits. A late receipt may retain fees after cancellation/lease loss, never publish a new result.';
create function medops_agent_runtime_guard() returns trigger language plpgsql as $$
begin
    if tg_op='DELETE' then
        if old.retained_until >= clock_timestamp() then
            raise exception 'agent runtime retention has not expired' using errcode='restrict_violation';
        end if;
        return old;
    end if;
    if tg_table_name='agent_runtime_events' then
        if tg_op='UPDATE' then
            raise exception 'agent runtime events are immutable' using errcode='restrict_violation';
        end if;
        if not exists(select 1 from agent_runtime_heads h where h.run_id=new.run_id
            and h.principal=new.principal and h.dept=new.dept and h.retained_until=new.retained_until) then
            raise exception 'agent runtime event owner mismatch' using errcode='restrict_violation';
        end if;
    elsif tg_op='INSERT' then
        if new.revision<>1 or not exists(select 1 from agent_run_control c where c.run_id=new.run_id
            and c.principal=new.principal and c.dept=new.dept and c.context_sha256=new.context_sha256
            and new.budget_deadline<=c.expires_at and new.retained_until>=c.expires_at) then
            raise exception 'agent runtime must start bound to original control' using errcode='restrict_violation';
        end if;
    else
        if row(new.run_id,new.principal,new.dept,new.context_sha256,new.budget_deadline,new.retained_until)
            is distinct from row(old.run_id,old.principal,old.dept,old.context_sha256,old.budget_deadline,old.retained_until)
            or new.revision<>old.revision+1 or new.lease_generation<old.lease_generation then
            raise exception 'agent runtime binding cannot reset' using errcode='restrict_violation';
        end if;
        if new.budget_state->'snapshot'->'limits' is distinct from old.budget_state->'snapshot'->'limits'
            or not ((new.budget_state->'settled') @> (old.budget_state->'settled'))
            or (new.budget_state->'snapshot'->>'accounted_tokens')::numeric < (old.budget_state->'snapshot'->>'accounted_tokens')::numeric
            or (new.budget_state->'snapshot'->>'known_tokens')::numeric < (old.budget_state->'snapshot'->>'known_tokens')::numeric
            or (new.budget_state->'snapshot'->>'accounted_cost_usd')::numeric < (old.budget_state->'snapshot'->>'accounted_cost_usd')::numeric
            or (new.budget_state->'snapshot'->>'known_cost_usd')::numeric < (old.budget_state->'snapshot'->>'known_cost_usd')::numeric
            or (new.budget_state->'snapshot'->>'calls')::numeric < (old.budget_state->'snapshot'->>'calls')::numeric then
            raise exception 'agent runtime accounting cannot reset' using errcode='restrict_violation';
        end if;
    end if;
    return new;
end $$;
create trigger agent_runtime_head_guard before insert or update or delete on agent_runtime_heads
    for each row execute function medops_agent_runtime_guard();
create trigger agent_runtime_event_guard before insert or update or delete on agent_runtime_events
    for each row execute function medops_agent_runtime_guard();
alter table agent_runtime_heads enable row level security;
alter table agent_runtime_heads force row level security;
alter table agent_runtime_events enable row level security;
alter table agent_runtime_events force row level security;
create policy agent_runtime_head_app on agent_runtime_heads for all to medops_app
    using(dept=medops_current_dept()) with check(dept=medops_current_dept());
create policy agent_runtime_event_app on agent_runtime_events for all to medops_app
    using(dept=medops_current_dept()) with check(dept=medops_current_dept());
create policy agent_runtime_head_retention on agent_runtime_heads for all to medops_restricted_role
    using(retained_until<clock_timestamp()) with check(false);
create policy agent_runtime_event_retention on agent_runtime_events for all to medops_restricted_role
    using(retained_until<clock_timestamp()) with check(false);
grant select,insert,update on agent_runtime_heads to medops_app;
grant select,insert on agent_runtime_events to medops_app;
grant select,delete on agent_runtime_heads,agent_runtime_events to medops_restricted_role;
""")


def downgrade() -> None:
    op.execute(
        "drop table agent_runtime_events; drop table agent_runtime_heads; drop function medops_agent_runtime_guard()"
    )
