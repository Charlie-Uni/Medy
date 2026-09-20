"""Transactional outbox for publish/archive events (M1-11; baseline 4.2 `outbox_events`, 5.1, 5.2).

Producers (the admin role, inside the same transaction as the status change) append events; consumers
(also the admin role for now: the index builders and, later, the cache invalidator) claim unpublished
events with `FOR UPDATE SKIP LOCKED`, do their idempotent work and record the (consumer, event) pair in
`outbox_consumer_acks`, so at-least-once delivery becomes exactly-once effect per consumer. Events are
append-only: payload and identity columns are immutable, rows cannot be deleted; only the delivery
bookkeeping columns change. Application and read-only roles have no access at all.

Revision ID: 0005
Revises: 0004
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UP = """
create table outbox_events (
    event_id        bigserial primary key,
    event_type      text not null check (event_type in ('document_activated', 'document_archived', 'document_withdrawn')),
    aggregate_type  text not null default 'document' check (aggregate_type = 'document'),
    aggregate_id    uuid not null,
    family_id       uuid not null,
    payload         jsonb not null,
    created_by      text not null,
    created_at      timestamptz not null default now(),
    published_at    timestamptz,
    attempts        integer not null default 0 check (attempts >= 0),
    last_error      text
);
comment on table outbox_events is 'M1-11 transactional outbox: written in the same transaction as the document status change; consumed at least once, acked per consumer.';
create index outbox_events_pending on outbox_events (event_id) where published_at is null;
create index outbox_events_family on outbox_events (family_id, event_id);

create table outbox_consumer_acks (
    consumer   text not null,
    event_id   bigint not null references outbox_events (event_id),
    acked_at   timestamptz not null default now(),
    primary key (consumer, event_id)
);
comment on table outbox_consumer_acks is 'Idempotency ledger: a consumer that already acked an event must not apply it again.';

create function medops_outbox_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'outbox events are append-only' using errcode = 'restrict_violation';
    end if;
    if new.event_id is distinct from old.event_id
       or new.event_type is distinct from old.event_type
       or new.aggregate_type is distinct from old.aggregate_type
       or new.aggregate_id is distinct from old.aggregate_id
       or new.family_id is distinct from old.family_id
       or new.payload is distinct from old.payload
       or new.created_by is distinct from old.created_by
       or new.created_at is distinct from old.created_at then
        raise exception 'outbox event identity and payload are immutable' using errcode = 'restrict_violation';
    end if;
    return new;
end $$;
create trigger outbox_events_guard before update or delete on outbox_events
    for each row execute function medops_outbox_guard();

create function medops_outbox_acks_guard() returns trigger language plpgsql as $$
begin
    raise exception 'consumer acks are append-only' using errcode = 'restrict_violation';
end $$;
create trigger outbox_consumer_acks_guard before update or delete on outbox_consumer_acks
    for each row execute function medops_outbox_acks_guard();

alter table outbox_events enable row level security;
alter table outbox_events force row level security;
alter table outbox_consumer_acks enable row level security;
alter table outbox_consumer_acks force row level security;
create policy outbox_events_admin_all on outbox_events for all to medops_admin_role using (true) with check (true);
create policy outbox_consumer_acks_admin_all on outbox_consumer_acks for all to medops_admin_role using (true) with check (true);
grant select, insert, update on outbox_events to medops_admin_role;
grant select, insert on outbox_consumer_acks to medops_admin_role;
grant usage, select on sequence outbox_events_event_id_seq to medops_admin_role;
"""

DOWN = """
drop table if exists outbox_consumer_acks;
drop table if exists outbox_events;
drop function if exists medops_outbox_acks_guard();
drop function if exists medops_outbox_guard();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
