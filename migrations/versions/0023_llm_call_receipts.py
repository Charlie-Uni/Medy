"""Bind spend reservations to calls and preserve metadata-only settlement receipts.

Revision ID: 0023
Revises: 0022
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

UP = """
alter table llm_spend_reservations
    add column call_context jsonb not null default '{}'::jsonb check (jsonb_typeof(call_context) = 'object'),
    add column call_receipt jsonb check (call_receipt is null or jsonb_typeof(call_receipt) = 'object');
create unique index llm_spend_call_id on llm_spend_reservations ((call_context->>'call_id'))
    where call_context ? 'call_id';
create index llm_spend_trace_id on llm_spend_reservations ((call_context->>'trace_id'))
    where call_context->>'trace_id' is not null;
comment on column llm_spend_reservations.call_receipt is
    'Metadata only. Reported-usage cost, conservative accounting and settlement status remain distinct; not a supplier invoice.';

create function medops_llm_reserve_call(
    p_month date, p_amount numeric, p_cap numeric, p_reservation uuid, p_context jsonb
) returns boolean language plpgsql security definer set search_path = pg_catalog, public as $$
declare field record;
begin
    if p_context is null or jsonb_typeof(p_context) <> 'object'
       or (p_context - array['call_id','trace_id','run_id','attempt_id','reservation_id','purpose','requested_model','provider']) <> '{}'::jsonb
       or coalesce(p_context->>'call_id','') = ''
       or p_context->>'reservation_id' is distinct from p_reservation::text
       or coalesce(p_context->>'purpose','') = ''
       or coalesce(p_context->>'requested_model','') = ''
       or coalesce(p_context->>'provider','') = '' then
        raise exception 'invalid LLM call context' using errcode = 'check_violation';
    end if;
    for field in select key,value from jsonb_each(p_context) loop
        if jsonb_typeof(field.value) not in ('string','null') then
            raise exception 'invalid LLM call context value' using errcode = 'check_violation';
        end if;
    end loop;
    if not medops_llm_reserve(p_month,p_amount,p_cap,p_reservation) then
        return false;
    end if;
    update llm_spend_reservations set call_context=p_context where reservation_id=p_reservation;
    return true;
end $$;

create function medops_llm_settle_call(p_reservation uuid, p_amount numeric, p_receipt jsonb)
returns numeric language plpgsql security definer set search_path = pg_catalog, public as $$
declare item llm_spend_reservations%rowtype;
declare total numeric;
declare field record;
begin
    select * into item from llm_spend_reservations where reservation_id=p_reservation for update;
    if not found then
        raise exception 'unknown LLM spend reservation' using errcode = 'no_data_found';
    end if;
    if p_receipt is null or jsonb_typeof(p_receipt) <> 'object'
       or (p_receipt - array['call','outcome','provider_started','estimated_cost_usd','actual_cost_usd',
           'accounted_cost_usd','cost_basis','settlement_status','usage','response_id','response_model','error_type','settlement_error_type']) <> '{}'::jsonb
       or p_receipt->'call' is distinct from item.call_context
       or p_receipt->>'settlement_status' is distinct from 'settled'
       or (p_receipt->>'accounted_cost_usd')::numeric is distinct from p_amount then
        raise exception 'LLM receipt does not match reservation' using errcode = 'check_violation';
    end if;
    for field in select key,value from jsonb_each(p_receipt) where key not in ('call','usage') loop
        if jsonb_typeof(field.value) not in ('string','number','boolean','null') then
            raise exception 'invalid LLM receipt value' using errcode = 'check_violation';
        end if;
    end loop;
    if p_receipt ? 'usage' and p_receipt->'usage' <> 'null'::jsonb then
        if jsonb_typeof(p_receipt->'usage') <> 'object'
           or ((p_receipt->'usage') - array['input_tokens','output_tokens','cached_input_tokens']) <> '{}'::jsonb then
            raise exception 'invalid LLM receipt usage' using errcode = 'check_violation';
        end if;
        for field in select key,value from jsonb_each(p_receipt->'usage') loop
            if jsonb_typeof(field.value) <> 'number' or field.value::text !~ '^[0-9]+$' then
                raise exception 'invalid LLM receipt token count' using errcode = 'check_violation';
            end if;
        end loop;
    end if;
    if item.call_receipt is not null then
        if item.call_receipt <> p_receipt then
            raise exception 'LLM call already has a different receipt' using errcode = 'restrict_violation';
        end if;
        select spent_usd into total from llm_monthly_spend where month=item.month;
        return total;
    end if;
    if item.status = 'settled' then
        -- The legacy amount column rounds to six decimals; the JSON receipt preserves the local price precision.
        if item.actual_usd <> round(p_amount,6) then
            raise exception 'LLM spend reservation already settled differently' using errcode = 'restrict_violation';
        end if;
        update llm_spend_reservations set call_receipt=p_receipt where reservation_id=p_reservation;
        select spent_usd into total from llm_monthly_spend where month=item.month;
        return total;
    end if;
    total := medops_llm_settle(p_reservation,p_amount);
    update llm_spend_reservations set call_receipt=p_receipt where reservation_id=p_reservation;
    return total;
end $$;

revoke all on function medops_llm_reserve_call(date,numeric,numeric,uuid,jsonb) from public;
revoke all on function medops_llm_settle_call(uuid,numeric,jsonb) from public;
grant execute on function medops_llm_reserve_call(date,numeric,numeric,uuid,jsonb) to medops_app, medops_admin_role;
grant execute on function medops_llm_settle_call(uuid,numeric,jsonb) to medops_app, medops_admin_role;
"""

DOWN = """
drop function medops_llm_settle_call(uuid,numeric,jsonb);
drop function medops_llm_reserve_call(date,numeric,numeric,uuid,jsonb);
drop index llm_spend_trace_id;
drop index llm_spend_call_id;
alter table llm_spend_reservations drop column call_receipt, drop column call_context;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
