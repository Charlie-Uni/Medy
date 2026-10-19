"""Read Agent material under the existing restricted role and DEC-013 boundary.

Revision ID: 0031
Revises: 0030
Additive SELECT policies only. Existing retention DELETE and app guards remain.
"""

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
grant select on agent_run_control to medops_restricted_role;
create policy agent_control_audit_read on agent_run_control for select to medops_restricted_role using(true);
create policy agent_head_audit_read on agent_runtime_heads for select to medops_restricted_role using(true);
create policy agent_event_audit_read on agent_runtime_events for select to medops_restricted_role using(true);
""")


def downgrade() -> None:
    op.execute("""
drop policy agent_event_audit_read on agent_runtime_events;
drop policy agent_head_audit_read on agent_runtime_heads;
drop policy agent_control_audit_read on agent_run_control;
revoke select on agent_run_control from medops_restricted_role;
""")
