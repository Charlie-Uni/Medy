"""M4-09 (record 85): a canary release is promoted step by step; the release log records `promote` next to `release`
and `rollback`. No new table: the current canary percentage of a released policy is the latest release / promote row.

Revision ID: 0018
Revises: 0017
"""

from __future__ import annotations

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

UP = r"""
alter table policy_releases drop constraint policy_releases_action_check;
alter table policy_releases add constraint policy_releases_action_check check (action in ('release', 'promote', 'rollback'));
comment on table policy_releases is 'Append-only release / promote / rollback log (baseline 4.2 policy_releases); the latest release or promote row of the released policy carries its canary percentage (M4-09).';
"""

DOWN = r"""
alter table policy_releases drop constraint policy_releases_action_check;
alter table policy_releases add constraint policy_releases_action_check check (action in ('release', 'rollback'));
comment on table policy_releases is 'Append-only release / rollback log (baseline 4.2 policy_releases).';
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
