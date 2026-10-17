"""One-time metadata-only budget handoffs, bound to the original Agent control row.

Revision ID: 0028
Revises: 0027

No automatic periodic checkpoint or crash replay is implied. Consumed images are
never claimable again; a new frozen root must supply the next revision.
"""

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
create table agent_budget_handoffs (
    run_id uuid primary key references agent_run_control(run_id),
    principal text not null,
    dept dept not null,
    revision bigint not null check (revision >= 1),
    checkpoint_id uuid not null,
    state_sha256 text not null check (state_sha256 ~ '^[0-9a-f]{64}$'),
    state jsonb not null check (octet_length(state::text) <= 2097152),
    budget_expires_at timestamptz not null,
    claimed_lease uuid,
    claimed_generation bigint check (claimed_generation >= 1),
    check ((claimed_lease is null) = (claimed_generation is null))
);
comment on table agent_budget_handoffs is 'Frozen budget metadata and single-consumer handoff; not Agent observations, authorization, provider reconciliation or full loop recovery.';
create function medops_agent_budget_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'budget handoff deletion requires a retention contract' using errcode = 'restrict_violation';
    elsif tg_op = 'INSERT' then
        if new.revision <> 1 or new.claimed_lease is not null then
            raise exception 'budget handoff must start unclaimed' using errcode = 'restrict_violation';
        end if;
    else
        if row(new.run_id,new.principal,new.dept) is distinct from row(old.run_id,old.principal,old.dept) then
            raise exception 'budget handoff owner is immutable' using errcode = 'restrict_violation';
        end if;
        if old.claimed_lease is null then
            if new.claimed_lease is null or
               row(new.revision,new.checkpoint_id,new.state_sha256,new.state,new.budget_expires_at)
               is distinct from row(old.revision,old.checkpoint_id,old.state_sha256,old.state,old.budget_expires_at) then
                raise exception 'only a one-time budget claim is allowed' using errcode = 'restrict_violation';
            end if;
        elsif new.revision <> old.revision + 1 or new.claimed_lease is not null
              or new.checkpoint_id = old.checkpoint_id or new.budget_expires_at > old.budget_expires_at then
            raise exception 'budget revision cannot reset or extend its deadline' using errcode = 'restrict_violation';
        end if;
    end if;
    return new;
end $$;
create trigger agent_budget_guard before insert or update or delete on agent_budget_handoffs
    for each row execute function medops_agent_budget_guard();
alter table agent_budget_handoffs enable row level security;
alter table agent_budget_handoffs force row level security;
create policy agent_budget_app on agent_budget_handoffs for all to medops_app
    using (dept=medops_current_dept()) with check (dept=medops_current_dept());
create policy agent_budget_admin_read on agent_budget_handoffs for select to medops_admin_role using (true);
grant select,insert,update on agent_budget_handoffs to medops_app;
grant select on agent_budget_handoffs to medops_admin_role;
""")


def downgrade() -> None:
    op.execute("drop table agent_budget_handoffs; drop function medops_agent_budget_guard()")
