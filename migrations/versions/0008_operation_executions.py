"""Operation-key persistence for harness nodes (M2-03; baseline 3.2, 4.2 `tasks/task_attempts` subset).

`operation_executions` holds one row per operation key: the key is claimed (inserted, status `running`)
before a node body runs, so two workers cannot execute the same operation twice; a succeeded row carries
the node's result for safe reuse; a failed row can be re-claimed (claim_no + 1). `run_kind` is derived from
the baseline rule production `run_id = trace_id`, replay `run_id = replay_run_id`: a replay never shares a
key with the production run because the key contains the run id, and the check constraint keeps the two
kinds from being confused in the table. `operation_attempts` records every attempt separately, per claim.

Succeeded rows are immutable, attempts are append-only. The application role writes both tables (the
harness runs under it); the admin role reads them for audit; the read-only role has no access. `result`
is a restricted payload (it can contain evidence text): its separate encrypted store is M3 (INV-OBS-03).

Revision ID: 0008
Revises: 0007
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

UP = """
create table operation_executions (
    operation_key   text primary key check (operation_key ~ '^[0-9a-f]{64}$'),
    operation_scope text not null,
    run_id          text not null,
    trace_id        text not null,
    run_kind        text not null check (run_kind in ('production', 'replay')),
    node_name       text not null,
    versions        jsonb not null,
    status          text not null check (status in ('running', 'succeeded', 'failed')),
    claim_no        integer not null default 1 check (claim_no >= 1),
    result          jsonb,
    error_code      text,
    claimed_at      timestamptz not null,
    finished_at     timestamptz,
    constraint operation_executions_result_iff_succeeded check ((status = 'succeeded') = (result is not null)),
    constraint operation_executions_failed_has_code check (status <> 'failed' or error_code is not null),
    constraint operation_executions_run_kind check ((run_kind = 'production') = (run_id = trace_id))
);
comment on table operation_executions is 'M2-03 idempotency ledger: one row per operation key (baseline 3.2); claimed before execution, result reused on repeat, replay runs never share a key with production.';
create index operation_executions_run on operation_executions (run_id, node_name);

create table operation_attempts (
    attempt_id     bigserial primary key,
    operation_key  text not null references operation_executions (operation_key),
    claim_no       integer not null check (claim_no >= 1),
    attempt        integer not null check (attempt >= 1),
    outcome        text not null check (outcome in ('ok', 'retry', 'failed', 'timeout')),
    error_code     text,
    detail         text not null default '',
    started_at     timestamptz not null,
    duration_ms    double precision not null check (duration_ms >= 0),
    unique (operation_key, claim_no, attempt)
);
comment on table operation_attempts is 'Every node attempt, recorded separately from the operation it belongs to (baseline 3.2: trace_id + node + attempt identifies an attempt, not an operation).';

create function medops_operation_executions_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'operation executions cannot be deleted' using errcode = 'restrict_violation';
    end if;
    if new.operation_key is distinct from old.operation_key
       or new.operation_scope is distinct from old.operation_scope
       or new.run_id is distinct from old.run_id
       or new.trace_id is distinct from old.trace_id
       or new.run_kind is distinct from old.run_kind
       or new.node_name is distinct from old.node_name
       or new.versions is distinct from old.versions then
        raise exception 'operation execution identity is immutable' using errcode = 'restrict_violation';
    end if;
    if old.status = 'succeeded' then
        raise exception 'a succeeded operation execution is immutable' using errcode = 'restrict_violation';
    end if;
    if new.claim_no < old.claim_no then
        raise exception 'claim_no never decreases' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;
create trigger operation_executions_guard before update or delete on operation_executions
    for each row execute function medops_operation_executions_guard();

create function medops_operation_attempts_guard() returns trigger language plpgsql as $$
begin
    raise exception 'operation attempts are append-only' using errcode = 'restrict_violation';
end $$;
create trigger operation_attempts_guard before update or delete on operation_attempts
    for each row execute function medops_operation_attempts_guard();

alter table operation_executions enable row level security;
alter table operation_executions force row level security;
alter table operation_attempts enable row level security;
alter table operation_attempts force row level security;
create policy operation_executions_app_all on operation_executions for all to medops_app using (true) with check (true);
create policy operation_attempts_app_all on operation_attempts for all to medops_app using (true) with check (true);
create policy operation_executions_admin_read on operation_executions for select to medops_admin_role using (true);
create policy operation_attempts_admin_read on operation_attempts for select to medops_admin_role using (true);
grant select, insert, update on operation_executions to medops_app;
grant select, insert on operation_attempts to medops_app;
grant usage, select on sequence operation_attempts_attempt_id_seq to medops_app;
grant select on operation_executions, operation_attempts to medops_admin_role;
"""

DOWN = """
drop table if exists operation_attempts;
drop table if exists operation_executions;
drop function if exists medops_operation_attempts_guard();
drop function if exists medops_operation_executions_guard();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
