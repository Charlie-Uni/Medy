"""Allow runtime roles to read aggregate LLM spend without exposing ledger rows.

Revision ID: 0021
Revises: 0020
"""

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

UP = """
create function medops_llm_month_total(p_month date)
returns numeric language plpgsql stable security definer set search_path = pg_catalog, public as $$
declare total numeric;
begin
    if p_month is null or p_month <> date_trunc('month', p_month)::date then
        raise exception 'invalid LLM spend month' using errcode = 'check_violation';
    end if;
    select coalesce((select spent_usd from llm_monthly_spend where month=p_month),0) into total;
    return total;
end $$;

revoke all on function medops_llm_month_total(date) from public;
grant execute on function medops_llm_month_total(date) to medops_app, medops_admin_role;
"""

DOWN = """
revoke execute on function medops_llm_month_total(date) from medops_app, medops_admin_role;
drop function medops_llm_month_total(date);
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
