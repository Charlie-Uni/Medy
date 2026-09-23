"""Server-side principal directory (M3-05; ADR-0001 §2/§3, INV-AUTH-01).

A verified token only identifies the user (`sub`); department, roles and scopes come from this table, keyed
by the HMAC pseudonym of `sub` (INV-OBS-02: no raw identity is stored). The application role may only read
it (the request handler resolves the caller before injecting the department into the transaction); the
admin role manages rows; the read-only MCP role has no access. Rows are never deleted, only deactivated.

Revision ID: 0009
Revises: 0008
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

UP = """
create function medops_scopes_valid(scopes text[]) returns boolean language sql immutable as $$
    select coalesce(bool_and(s ~ '^(MA|PV|CO|ADMIN):[a-z_]+$'), true) from unnest(scopes) s
$$;

create table principals (
    sub_pseudonym  text primary key check (sub_pseudonym ~ '^[0-9a-f]{64}$'),
    dept           dept not null,
    roles          text[] not null default '{}',
    scopes         text[] not null default '{}',
    active         boolean not null default true,
    created_by     text not null,
    created_at     timestamptz not null default now(),
    updated_at     timestamptz not null default now(),
    note           text not null default '',
    constraint principals_scopes_shape check (medops_scopes_valid(scopes))
);
comment on table principals is 'M3-05 directory: token sub (HMAC pseudonym) -> department, roles, scopes. Server-side mapping only (ADR-0001); never a raw identity.';

create function medops_principals_guard() returns trigger language plpgsql as $$
begin
    if tg_op = 'DELETE' then
        raise exception 'principals are deactivated, never deleted' using errcode = 'restrict_violation';
    end if;
    if new.sub_pseudonym is distinct from old.sub_pseudonym or new.created_at is distinct from old.created_at
       or new.created_by is distinct from old.created_by then
        raise exception 'principal identity is immutable' using errcode = 'restrict_violation';
    end if;
    new.updated_at := now();
    return new;
end $$;
create trigger principals_guard before update or delete on principals
    for each row execute function medops_principals_guard();

alter table principals enable row level security;
alter table principals force row level security;
create policy principals_app_read on principals for select to medops_app using (true);
create policy principals_admin_all on principals for all to medops_admin_role using (true) with check (true);
grant select on principals to medops_app;
grant select, insert, update on principals to medops_admin_role;
"""

DOWN = """
drop table if exists principals;
drop function if exists medops_principals_guard();
drop function if exists medops_scopes_valid(text[]);
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
