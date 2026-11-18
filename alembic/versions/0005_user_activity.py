"""user activity (active users on the admin overview)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18 12:00:00

Data: past activity is rebuilt from what already has a timestamp (sign-up, sign-ins still on record, payments),
one row per user per UTC day at the earliest of those moments. Activity from now on is written by app/activity.py.
"""
from datetime import timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    activity = op.create_table(
        'user_activity',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'day'),
    )
    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_activity_seen_at'), ['seen_at'], unique=False)

    # Backfill (migrations never import app code: lightweight tables only)
    def source(name, who):
        return sa.table(name, sa.column(who, sa.Integer), sa.column('created_at', sa.DateTime(timezone=True))), who

    bind = op.get_bind()
    first_seen = {}
    for table, who in (source('users', 'id'), source('sessions', 'user_id'), source('payments', 'student_id')):
        for user_id, ts in bind.execute(sa.select(table.c[who], table.c.created_at)):
            if user_id is None or ts is None:
                continue
            ts = ts.replace(tzinfo=timezone.utc) if ts.tzinfo is None else ts.astimezone(timezone.utc)
            key = (user_id, ts.date())
            if key not in first_seen or ts < first_seen[key]:
                first_seen[key] = ts
    if first_seen:
        op.bulk_insert(activity, [{'user_id': u, 'day': d, 'seen_at': ts} for (u, d), ts in first_seen.items()])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('user_activity', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_activity_seen_at'))
    op.drop_table('user_activity')
