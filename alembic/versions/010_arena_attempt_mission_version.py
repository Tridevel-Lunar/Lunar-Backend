"""add mission_version to arena_attempts if missing (legacy 009 installs)

Revision ID: 010_arena_mission_ver
Revises: 009_arena_attempts
Create Date: 2026-07-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_arena_mission_ver"
down_revision: Union[str, None] = "009_arena_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "arena_attempts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("arena_attempts")}
    if "mission_version" not in columns:
        op.add_column(
            "arena_attempts",
            sa.Column("mission_version", sa.Integer(), nullable=False, server_default="1"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "arena_attempts" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("arena_attempts")}
    if "mission_version" in columns:
        op.drop_column("arena_attempts", "mission_version")
