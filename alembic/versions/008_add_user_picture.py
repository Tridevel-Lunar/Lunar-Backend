"""add picture column to users table for Google profile photo

Revision ID: 008_add_user_picture
Revises: 007_create_refresh_tokens
Create Date: 2026-07-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_add_user_picture"
down_revision: Union[str, None] = "007_create_refresh_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("picture", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "picture")
