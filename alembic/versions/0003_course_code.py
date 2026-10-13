"""course code on groups

Adds groups.code (unique, uppercase, e.g. "EN-101"), backfilling a code for every existing group with the same
scheme the app uses for new groups (app.services.generate_course_code).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-13
"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _prefix(category: str, subject: str) -> str:
    # Kept in sync with app.services.course_code_prefix (migrations must not import app code).
    if category == "language":
        return subject.upper()[:3]
    letters = re.sub(r"[^A-Za-z]", "", subject).upper()
    return letters[:3] if len(letters) >= 2 else "CRS"


def upgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.add_column(sa.Column("code", sa.String(length=20), nullable=True))

    groups = sa.table(
        "groups", sa.column("id", sa.Integer), sa.column("code", sa.String),
        sa.column("category", sa.String), sa.column("subject", sa.String),
    )
    conn = op.get_bind()
    taken: set[str] = set()
    for gid, category, subject in conn.execute(
        sa.select(groups.c.id, groups.c.category, groups.c.subject).order_by(groups.c.id)
    ).all():
        prefix, n = _prefix(category, subject), 101
        while f"{prefix}-{n}" in taken:
            n += 1
        taken.add(f"{prefix}-{n}")
        conn.execute(groups.update().where(groups.c.id == gid).values(code=f"{prefix}-{n}"))

    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.alter_column("code", existing_type=sa.String(length=20), nullable=False)
        batch_op.create_index(batch_op.f("ix_groups_code"), ["code"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("groups", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_groups_code"))
        batch_op.drop_column("code")
