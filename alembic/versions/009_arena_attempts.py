"""arena attempts JSONB for Blockly AST drafts

Revision ID: 009_arena_attempts
Revises: 008_add_user_picture
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "009_arena_attempts"
down_revision: Union[str, None] = "008_add_user_picture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "arena_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", sa.String(length=64), nullable=False),
        sa.Column("ast", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("mission_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "mission_id", name="uq_arena_attempts_user_mission"),
    )
    op.create_index("ix_arena_attempts_user_id", "arena_attempts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_arena_attempts_user_id", table_name="arena_attempts")
    op.drop_table("arena_attempts")
