"""tutor documents

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12 21:03:29.162080

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('tutor_documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tutor_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=64), nullable=False),
    sa.Column('original_name', sa.String(length=160), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['tutor_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tutor_documents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tutor_documents_tutor_id'), ['tutor_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tutor_review_note', sa.String(length=500), server_default='', nullable=False))



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('tutor_review_note')

    with op.batch_alter_table('tutor_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tutor_documents_tutor_id'))

    op.drop_table('tutor_documents')
