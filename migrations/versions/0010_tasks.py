"""Asynchronous skill tasks (M3-02/04; baseline 3.2 HTTP idempotency, 4.2 `tasks/task_attempts`, 5.7).

`tasks` is the source of truth for task state (queued -> running -> completed | failed; a failed, retryable task
may be re-queued). A worker claims a task with an atomic status transition plus a lease; an expired lease makes
the task claimable again, so a crashed worker never strands it and duplicate consumption is bounded by the
lease and the operation-key ledger (M2-03). Every attempt is a separate row. `idempotency_keys` scopes a
client key by principal + route and stores the canonical request hash: same key + same payload returns the
original task, a different payload is a 422 (contract). Application role reads/writes these tables; the
read-only role has no access; the admin role reads for audit.

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UP = """
create table tasks (
    task_id        uuid primary key,
    principal      text not null check (principal ~ '^[0-9a-f]{32,64}$'),
    dept           dept not null,
    skill_name     text not null check (skill_name ~ '^[a-z][a-z0-9_]{2,63}$'),
    skill_version  text not null,
    input          jsonb not null,
    historical     jsonb,
    status         text not null check (status in ('queued', 'running', 'completed', 'failed')),
    attempts       integer not null default 0 check (attempts >= 0),
    max_attempts   integer not null default 3 check (max_attempts >= 1),
    lease_owner    text,
    lease_until    timestamptz,
    trace_id       text check (trace_id ~ '^[0-9a-f]{32}$'),
    result         jsonb,
    error          jsonb,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    constraint tasks_completed_shape check (status <> 'completed' or (result is not null and error is null)),
    constraint tasks_failed_shape check (status <> 'failed' or (error is not null and result is null)),
    constraint tasks_open_shape check (status not in ('queued', 'running') or (result is null and error is null)),
    constraint tasks_running_has_lease check (status <> 'running' or (lease_owner is not null and lease_until is not null))
);
comment on table tasks is 'M3-02 asynchronous skill tasks: PostgreSQL is the source of truth; queued/running/completed/failed; leases bound duplicate consumption.';
create index tasks_claimable on tasks (created_at) where status in ('queued', 'running');
create index tasks_by_principal on tasks (principal, created_at desc);

create table task_attempts (
    attempt_id   bigserial primary key,
    task_id      uuid not null references tasks (task_id),
    attempt      integer not null check (attempt >= 1),
    worker       text not null,
    started_at   timestamptz not null default now(),
    finished_at  timestamptz,
    outcome      text not null default 'running' check (outcome in ('running', 'completed', 'failed', 'lost')),
    error_code   text,
    trace_id     text check (trace_id ~ '^[0-9a-f]{32}$'),
    unique (task_id, attempt)
);
comment on table task_attempts is 'One row per worker attempt of a task; lost = lease expired before the worker reported.';

create table idempotency_keys (
    principal     text not null check (principal ~ '^[0-9a-f]{32,64}$'),
    route         text not null,
    key           text not null check (length(key) between 1 and 255),
    request_hash  text not null check (request_hash ~ '^[0-9a-f]{64}$'),
    task_id       uuid references tasks (task_id),
    receipt       jsonb,
    created_at    timestamptz not null default now(),
    expires_at    timestamptz not null,
    primary key (principal, route, key),
    constraint idempotency_target check ((task_id is not null) <> (receipt is not null))
);
comment on table idempotency_keys is 'Baseline 3.2 HTTP idempotency: scope = principal + route + key; canonical request hash; points at the task or stores the receipt.';
create index idempotency_expiry on idempotency_keys (expires_at);

create function medops_tasks_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'tasks are never deleted' using errcode = 'restrict_violation';
    end if;
    if new.task_id is distinct from old.task_id or new.principal is distinct from old.principal
       or new.dept is distinct from old.dept or new.skill_name is distinct from old.skill_name
       or new.skill_version is distinct from old.skill_version or new.input is distinct from old.input
       or new.created_at is distinct from old.created_at then
        raise exception 'task identity and input are immutable' using errcode = 'restrict_violation';
    end if;
    if old.status = 'completed' then
        raise exception 'a completed task is immutable' using errcode = 'restrict_violation';
    end if;
    if old.status = 'failed' and new.status not in ('failed', 'queued') then
        raise exception 'a failed task can only be re-queued' using errcode = 'restrict_violation';
    end if;
    new.updated_at := now();
    return new;
end $$;
create trigger tasks_guard before update or delete on tasks for each row execute function medops_tasks_guard();

create function medops_append_only() returns trigger language plpgsql as $$
begin
    raise exception 'append-only table' using errcode = 'restrict_violation';
end $$;
create trigger idempotency_keys_guard before update or delete on idempotency_keys for each row execute function medops_append_only();

alter table tasks enable row level security;
alter table tasks force row level security;
alter table task_attempts enable row level security;
alter table task_attempts force row level security;
alter table idempotency_keys enable row level security;
alter table idempotency_keys force row level security;
create policy tasks_app_all on tasks for all to medops_app using (true) with check (true);
create policy task_attempts_app_all on task_attempts for all to medops_app using (true) with check (true);
create policy idempotency_keys_app_all on idempotency_keys for all to medops_app using (true) with check (true);
create policy tasks_admin_read on tasks for select to medops_admin_role using (true);
create policy task_attempts_admin_read on task_attempts for select to medops_admin_role using (true);
create policy idempotency_keys_admin_read on idempotency_keys for select to medops_admin_role using (true);
grant select, insert, update on tasks to medops_app;
grant select, insert, update on task_attempts to medops_app;
grant select, insert on idempotency_keys to medops_app;
grant usage, select on sequence task_attempts_attempt_id_seq to medops_app;
grant select on tasks, task_attempts, idempotency_keys to medops_admin_role;
"""

DOWN = """
drop table if exists idempotency_keys;
drop table if exists task_attempts;
drop table if exists tasks;
drop function if exists medops_append_only();
drop function if exists medops_tasks_guard();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
