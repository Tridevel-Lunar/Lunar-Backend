"""add workspace JSON column to arena_attempts

Revision ID: 011_arena_workspace
Revises: 010_arena_mission_ver
Create Date: 2026-07-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011_arena_workspace"
down_revision: Union[str, None] = "010_arena_mission_ver"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "arena_attempts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("arena_attempts")}
    if "workspace" in columns:
        return
    op.add_column(
        "arena_attempts",
        sa.Column(
            "workspace",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "arena_attempts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("arena_attempts")}
    if "workspace" in columns:
        op.drop_column("arena_attempts", "workspace")
