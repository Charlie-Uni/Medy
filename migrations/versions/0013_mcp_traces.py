"""MCP tool calls are requests too (M3-07 follow-up, records 62/72): every read-only tool call writes a trace of
`kind = 'mcp'` through the application role, fail-closed like /v1/ask. No new table.

Revision ID: 0013
Revises: 0012
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

UP = """
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ('ask', 'task', 'replay', 'mcp'));
"""

DOWN = """
delete from trace_spans where trace_id in (select trace_id from traces where kind = 'mcp');
delete from traces where kind = 'mcp';
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ('ask', 'task', 'replay'));
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
