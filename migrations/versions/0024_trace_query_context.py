"""Preserve the effective query day and explicit historical mode, without body data.

Revision ID: 0024
Revises: 0023
"""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

UP = """
alter table traces add column query_context jsonb;
alter table traces add constraint traces_query_context_shape check (
    query_context is null or (
        jsonb_typeof(query_context) = 'object'
        and query_context ?& array['as_of','historical_requested']
        and query_context - array['as_of','historical_requested'] = '{}'::jsonb
        and jsonb_typeof(query_context->'as_of') = 'string'
        and (query_context->>'as_of') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
        and (query_context->>'as_of')::date is not null
        and jsonb_typeof(query_context->'historical_requested') = 'boolean'
    )
);
comment on column traces.query_context is
    'Effective date and explicit archival mode only. NULL means unknown legacy input; do not infer it. Not a historical fact snapshot.';
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute("alter table traces drop column query_context")
