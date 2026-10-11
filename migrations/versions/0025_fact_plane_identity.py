"""Persist the fact-plane identity independently of a PostgreSQL process lifetime.

Revision ID: 0025
Revises: 0024
"""

from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

UP = """
create table fact_plane_identity (
    singleton boolean primary key default true check (singleton),
    fact_plane_id uuid not null unique default gen_random_uuid()
        check (fact_plane_id <> '00000000-0000-0000-0000-000000000000'::uuid),
    created_at timestamptz not null default now()
);
insert into fact_plane_identity(singleton) values (true);
comment on table fact_plane_identity is
    'Stable audit source, not a runtime/readiness fingerprint. Preserve on disaster recovery; explicitly rotate on an independent clone before exporting feedback.';
alter table fact_plane_identity enable row level security;
alter table fact_plane_identity force row level security;
create policy fact_plane_identity_audit_read on fact_plane_identity
    for select to medops_admin_role, medops_loop_role using (true);
grant select on fact_plane_identity to medops_admin_role, medops_loop_role;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute("drop table fact_plane_identity")
