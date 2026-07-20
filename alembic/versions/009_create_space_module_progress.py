"""create space_module_progress table

Revision ID: 009_space_module_progress
Revises: 008_add_user_picture
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_space_module_progress"
down_revision: Union[str, None] = "008_add_user_picture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "space_module_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", sa.String(length=64), nullable=False),
        sa.Column("module_id", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "course_id", "module_id", name="uq_space_module_progress"),
    )
    op.create_index(
        op.f("ix_space_module_progress_user_id"),
        "space_module_progress",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_space_module_progress_user_id"), table_name="space_module_progress")
    op.drop_table("space_module_progress")
