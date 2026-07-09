"""add user role for RBAC

Revision ID: 005_user_role
Revises: 004_knowledge_source_manifest
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_user_role"
down_revision: Union[str, None] = "004_knowledge_source_manifest"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="learner"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
