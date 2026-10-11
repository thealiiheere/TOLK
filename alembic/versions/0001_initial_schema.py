"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-11 23:49:36.525915

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('telegram_id', sa.BigInteger(), nullable=True),
    sa.Column('telegram_username', sa.String(length=64), nullable=True),
    sa.Column('photo_url', sa.String(length=500), nullable=True),
    sa.Column('full_name', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('lang', sa.String(length=2), nullable=False),
    sa.Column('onboarded', sa.Boolean(), nullable=False),
    sa.Column('bio', sa.Text(), nullable=False),
    sa.Column('tutor_subjects', sa.String(length=255), nullable=False),
    sa.Column('tutor_status', sa.String(length=16), nullable=True),
    sa.Column('is_blocked', sa.Boolean(), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("role IN ('student','tutor','admin')", name='ck_users_role'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_telegram_id'), ['telegram_id'], unique=True)

    op.create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('category', sa.String(length=16), nullable=False),
    sa.Column('subject', sa.String(length=80), nullable=False),
    sa.Column('level', sa.String(length=40), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('price', sa.Integer(), nullable=False),
    sa.Column('price_period', sa.String(length=16), nullable=False),
    sa.Column('schedule', sa.String(length=160), nullable=False),
    sa.Column('max_students', sa.Integer(), nullable=False),
    sa.Column('tutor_id', sa.Integer(), nullable=True),
    sa.Column('is_published', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("category IN ('language','other')", name='ck_groups_category'),
    sa.CheckConstraint('price >= 0', name='ck_groups_price'),
    sa.ForeignKeyConstraint(['tutor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_groups_subject'), ['subject'], unique=False)
        batch_op.create_index(batch_op.f('ix_groups_tutor_id'), ['tutor_id'], unique=False)

    op.create_table('sessions',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('token_hash')
    )
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sessions_user_id'), ['user_id'], unique=False)

    op.create_table('group_students',
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('strikes', sa.Integer(), nullable=False),
    sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('group_id', 'student_id')
    )
    op.create_table('homework_submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('link', sa.String(length=500), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('homework_submissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_homework_submissions_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_homework_submissions_student_id'), ['student_id'], unique=False)

    op.create_table('lessons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('tutor_id', sa.Integer(), nullable=True),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('duration_min', sa.Integer(), nullable=False),
    sa.Column('topic', sa.String(length=200), nullable=False),
    sa.Column('meet_link', sa.String(length=500), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tutor_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lessons_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lessons_starts_at'), ['starts_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_lessons_tutor_id'), ['tutor_id'], unique=False)

    op.create_table('payments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Integer(), nullable=False),
    sa.Column('receipt_filename', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('admin_comment', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_payments_group_id'), ['group_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_payments_student_id'), ['student_id'], unique=False)

    op.create_table('lesson_ratings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lesson_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('tutor_id', sa.Integer(), nullable=False),
    sa.Column('stars', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint('stars BETWEEN 1 AND 5', name='ck_lesson_ratings_stars'),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tutor_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lesson_id', 'student_id', name='uq_lesson_ratings_lesson_student')
    )
    with op.batch_alter_table('lesson_ratings', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lesson_ratings_lesson_id'), ['lesson_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lesson_ratings_student_id'), ['student_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lesson_ratings_tutor_id'), ['tutor_id'], unique=False)

    op.create_table('lesson_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lesson_id', sa.Integer(), nullable=False),
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('attended', sa.Boolean(), nullable=False),
    sa.Column('hw_status', sa.String(length=16), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lesson_id', 'student_id', name='uq_lesson_records_lesson_student')
    )
    with op.batch_alter_table('lesson_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lesson_records_lesson_id'), ['lesson_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lesson_records_student_id'), ['student_id'], unique=False)



def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('lesson_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lesson_records_student_id'))
        batch_op.drop_index(batch_op.f('ix_lesson_records_lesson_id'))

    op.drop_table('lesson_records')
    with op.batch_alter_table('lesson_ratings', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lesson_ratings_tutor_id'))
        batch_op.drop_index(batch_op.f('ix_lesson_ratings_student_id'))
        batch_op.drop_index(batch_op.f('ix_lesson_ratings_lesson_id'))

    op.drop_table('lesson_ratings')
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_payments_student_id'))
        batch_op.drop_index(batch_op.f('ix_payments_status'))
        batch_op.drop_index(batch_op.f('ix_payments_group_id'))

    op.drop_table('payments')
    with op.batch_alter_table('lessons', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lessons_tutor_id'))
        batch_op.drop_index(batch_op.f('ix_lessons_starts_at'))
        batch_op.drop_index(batch_op.f('ix_lessons_group_id'))

    op.drop_table('lessons')
    with op.batch_alter_table('homework_submissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_homework_submissions_student_id'))
        batch_op.drop_index(batch_op.f('ix_homework_submissions_group_id'))

    op.drop_table('homework_submissions')
    op.drop_table('group_students')
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_user_id'))

    op.drop_table('sessions')
    with op.batch_alter_table('groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_groups_tutor_id'))
        batch_op.drop_index(batch_op.f('ix_groups_subject'))

    op.drop_table('groups')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_telegram_id'))

    op.drop_table('users')
