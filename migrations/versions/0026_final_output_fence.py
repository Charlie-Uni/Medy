"""Serialize the short final output check with ordinary fact/identity mutations.

Revision ID: 0026
Revises: 0025

Shared output locks end at audit/result commit; statement triggers take an exclusive
transaction lock before fact changes. No row write privilege is granted to readers.
Migration owners can disable triggers: they remain trusted operators, not tenants.
"""

from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

TABLES = ("principals", "document_acl", "documents", "source_objects", "chunks", "chunk_spans")
# Database-scoped advisory key reserved for the output/fact mutation boundary.
LOCK_KEY = 21749715913086032


def upgrade() -> None:
    op.execute("alter table tasks add column output_binding jsonb")
    op.execute("""
create function medops_task_output_binding_guard() returns trigger
language plpgsql as $$
begin
    if tg_op = 'INSERT' and new.output_binding is not null then
        raise exception 'task output binding requires completion';
    elsif tg_op = 'UPDATE' and new.output_binding is distinct from old.output_binding
       and not (old.status = 'running' and new.status = 'completed' and new.result is not null) then
        raise exception 'task output binding is immutable';
    end if;
    return new;
end $$;
create trigger task_output_binding_guard before insert or update on tasks
    for each row execute function medops_task_output_binding_guard();
""")
    op.execute(f"""
create function medops_acquire_output_fence() returns void
language plpgsql security invoker set search_path = pg_catalog, public as $$
begin
    if current_setting('transaction_isolation') <> 'read committed' then
        raise exception 'final output requires read committed' using errcode = '55000';
    end if;
    perform pg_advisory_xact_lock_shared({LOCK_KEY}::bigint);
end $$;
revoke all on function medops_acquire_output_fence() from public;
grant execute on function medops_acquire_output_fence() to medops_app, medops_readonly;
create function medops_facts_write_fence() returns trigger
language plpgsql security invoker set search_path = pg_catalog, public as $$
begin
    perform pg_advisory_xact_lock({LOCK_KEY}::bigint);
    return null;
end $$;
revoke all on function medops_facts_write_fence() from public;
""")
    for table in TABLES:
        op.execute(
            f"create trigger final_output_write_fence before insert or update or delete or truncate on {table} for each statement execute function medops_facts_write_fence()"
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"drop trigger final_output_write_fence on {table}")
    op.execute("drop function medops_facts_write_fence(); drop function medops_acquire_output_fence()")
    op.execute(
        "drop trigger task_output_binding_guard on tasks; drop function medops_task_output_binding_guard(); alter table tasks drop column output_binding"
    )
