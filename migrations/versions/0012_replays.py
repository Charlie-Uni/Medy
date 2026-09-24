"""Trace replays (M3-08; baseline 3.2 replay_run_id, 5.7 replay endpoint).

A replay is itself a trace (`kind = 'replay'`), recorded like any request; `replays` links it to the source
trace with the diff report and who asked. Append-only; application role writes, admin role reads.

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

UP = """
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ('ask', 'task', 'replay'));

create table replays (
    replay_id        uuid primary key,
    source_trace_id  text not null references traces (trace_id),
    replay_trace_id  text not null unique references traces (trace_id),
    replay_run_id    text not null check (replay_run_id ~ '^[0-9a-f]{32}$'),
    requested_by     text not null,
    reason           text not null,
    versions_match   boolean not null,
    changed          text[] not null default '{}',
    report           jsonb not null,
    created_at       timestamptz not null default now(),
    constraint replays_distinct check (source_trace_id <> replay_trace_id)
);
comment on table replays is 'M3-08: one row per admin replay of a trace; the replay trace has kind=replay and a run id distinct from the source run.';
create index replays_source on replays (source_trace_id, created_at desc);
create trigger replays_guard before update or delete on replays for each row execute function medops_append_only();

alter table replays enable row level security;
alter table replays force row level security;
create policy replays_app on replays for all to medops_app using (true) with check (true);
create policy replays_admin on replays for select to medops_admin_role using (true);
grant select, insert on replays to medops_app;
grant select on replays to medops_admin_role;
"""

DOWN = """
drop table if exists replays;
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ('ask', 'task'));
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
