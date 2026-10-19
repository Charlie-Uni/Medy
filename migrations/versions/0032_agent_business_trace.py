"""Add body-free Agent terminal metadata to the existing append-only Trace.

Revision ID: 0032
Revises: 0031

No ACL, existing Trace values, frozen evaluation or runtime envelope changes.
Downgrade refuses retained Agent rows rather than deleting audit/feedback.
"""

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None

OLD_KINDS = "'ask', 'task', 'replay', 'mcp'"
OLD_OUTCOMES = "'answered', 'refused', 'escalated', 'completed', 'insufficient_evidence', 'failed'"


def upgrade() -> None:
    op.execute(f"""
alter table traces add column agent_metadata jsonb;
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ({OLD_KINDS}, 'agent'));
alter table traces drop constraint traces_outcome_check;
alter table traces add constraint traces_outcome_check
    check (outcome in ({OLD_OUTCOMES}, 'awaiting_clarification', 'cancelled'));
alter table traces add constraint traces_agent_metadata_check check (
    (kind = 'agent') = (agent_metadata is not null)
    and (kind <> 'agent' or coalesce(
        jsonb_typeof(agent_metadata) = 'object'
        and agent_metadata->>'schema_version' = 'pv-agent-trace-v1', false))
);
alter table traces add constraint traces_agent_outcome_check check (
    (kind = 'agent' and outcome in ('completed','awaiting_clarification','escalated','failed','cancelled'))
    or (kind <> 'agent' and outcome in ({OLD_OUTCOMES}))
);
comment on column traces.agent_metadata is
    'Agent terminal identifiers, actual versions and accounted/known/reserved budget. No narrative, prompt, model reply or evidence text. NULL for legacy kinds.';
""")


def downgrade() -> None:
    op.execute(f"""
do $$ begin
    if exists(select 1 from traces where kind = 'agent') then
        raise exception 'retained Agent traces prevent downgrade' using errcode = 'restrict_violation';
    end if;
end $$;
alter table traces drop constraint traces_agent_outcome_check;
alter table traces drop constraint traces_agent_metadata_check;
alter table traces drop column agent_metadata;
alter table traces drop constraint traces_kind_check;
alter table traces add constraint traces_kind_check check (kind in ({OLD_KINDS}));
alter table traces drop constraint traces_outcome_check;
alter table traces add constraint traces_outcome_check check (outcome in ({OLD_OUTCOMES}));
""")
