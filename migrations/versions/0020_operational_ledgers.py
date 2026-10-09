"""Operational ledgers: per-consumer outbox dead letters and durable LLM spend reservations.

Revision ID: 0020
Revises: 0019
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

UP = """
create table outbox_consumer_failures (
    consumer          text not null,
    event_id           bigint not null references outbox_events(event_id),
    attempts           integer not null default 0 check (attempts >= 0),
    last_error         text,
    next_attempt_at    timestamptz not null default now(),
    dead_lettered_at   timestamptz,
    requeued_at        timestamptz,
    requeued_by        text,
    updated_at         timestamptz not null default now(),
    primary key (consumer, event_id),
    check ((requeued_at is null) = (requeued_by is null))
);
comment on table outbox_consumer_failures is 'Per-consumer retry and dead-letter state. A dead letter remains unacknowledged until an operator requeues it.';
create index outbox_consumer_failures_due on outbox_consumer_failures
    (consumer, next_attempt_at, event_id) where dead_lettered_at is null;
alter table outbox_consumer_failures enable row level security;
alter table outbox_consumer_failures force row level security;
create policy outbox_consumer_failures_admin_all on outbox_consumer_failures
    for all to medops_admin_role using (true) with check (true);
grant select, insert, update on outbox_consumer_failures to medops_admin_role;

create table llm_monthly_spend (
    month          date primary key check (month = date_trunc('month', month)::date),
    spent_usd      numeric(14,6) not null default 0 check (spent_usd >= 0),
    reserved_usd   numeric(14,6) not null default 0 check (reserved_usd >= 0),
    updated_at     timestamptz not null default now()
);
create table llm_spend_reservations (
    reservation_id uuid primary key,
    month           date not null references llm_monthly_spend(month),
    reserved_usd    numeric(14,6) not null check (reserved_usd >= 0),
    actual_usd      numeric(14,6) check (actual_usd >= 0),
    status          text not null default 'reserved' check (status in ('reserved', 'settled')),
    created_at      timestamptz not null default now(),
    settled_at      timestamptz,
    check ((status = 'reserved' and actual_usd is null and settled_at is null)
        or (status = 'settled' and actual_usd is not null and settled_at is not null))
);
comment on table llm_spend_reservations is 'Fail-closed call reservations. A process crash leaves a visible reservation for operator reconciliation.';
alter table llm_monthly_spend enable row level security;
alter table llm_monthly_spend force row level security;
alter table llm_spend_reservations enable row level security;
alter table llm_spend_reservations force row level security;
create policy llm_monthly_spend_admin_select on llm_monthly_spend for select to medops_admin_role using (true);
create policy llm_spend_reservations_admin_select on llm_spend_reservations for select to medops_admin_role using (true);
grant select on llm_monthly_spend, llm_spend_reservations to medops_admin_role;

create function medops_llm_reserve(p_month date, p_amount numeric, p_cap numeric, p_reservation uuid)
returns boolean language plpgsql security definer set search_path = pg_catalog, public as $$
declare totals llm_monthly_spend%rowtype;
begin
    if p_month is null or p_month <> date_trunc('month', p_month)::date
       or p_amount is null or p_amount < 0 or p_cap is null or p_cap < 0 then
        raise exception 'invalid LLM spend reservation' using errcode = 'check_violation';
    end if;
    insert into llm_monthly_spend(month) values (p_month) on conflict do nothing;
    select * into totals from llm_monthly_spend where month=p_month for update;
    if totals.spent_usd + totals.reserved_usd + p_amount > p_cap then
        return false;
    end if;
    insert into llm_spend_reservations(reservation_id,month,reserved_usd)
        values (p_reservation,p_month,p_amount);
    update llm_monthly_spend set reserved_usd=reserved_usd+p_amount,updated_at=now() where month=p_month;
    return true;
end $$;

create function medops_llm_settle(p_reservation uuid, p_actual numeric)
returns numeric language plpgsql security definer set search_path = pg_catalog, public as $$
declare item llm_spend_reservations%rowtype;
declare total numeric;
begin
    if p_actual is null or p_actual < 0 then
        raise exception 'invalid LLM spend settlement' using errcode = 'check_violation';
    end if;
    select * into item from llm_spend_reservations where reservation_id=p_reservation for update;
    if not found then
        raise exception 'unknown LLM spend reservation' using errcode = 'no_data_found';
    end if;
    if item.status = 'settled' then
        if item.actual_usd <> p_actual then
            raise exception 'LLM spend reservation already settled differently' using errcode = 'restrict_violation';
        end if;
        select spent_usd into total from llm_monthly_spend where month=item.month;
        return total;
    end if;
    update llm_monthly_spend
       set reserved_usd=reserved_usd-item.reserved_usd,spent_usd=spent_usd+p_actual,updated_at=now()
     where month=item.month returning spent_usd into total;
    update llm_spend_reservations
       set actual_usd=p_actual,status='settled',settled_at=now() where reservation_id=p_reservation;
    return total;
end $$;

revoke all on function medops_llm_reserve(date,numeric,numeric,uuid) from public;
revoke all on function medops_llm_settle(uuid,numeric) from public;
grant execute on function medops_llm_reserve(date,numeric,numeric,uuid) to medops_app, medops_admin_role;
grant execute on function medops_llm_settle(uuid,numeric) to medops_app, medops_admin_role;
"""

DOWN = """
revoke execute on function medops_llm_settle(uuid,numeric) from medops_app, medops_admin_role;
revoke execute on function medops_llm_reserve(date,numeric,numeric,uuid) from medops_app, medops_admin_role;
drop function medops_llm_settle(uuid,numeric);
drop function medops_llm_reserve(date,numeric,numeric,uuid);
drop table llm_spend_reservations;
drop table llm_monthly_spend;
drop table outbox_consumer_failures;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
