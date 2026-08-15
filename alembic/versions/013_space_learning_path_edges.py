"""add edges JSON column to space_learning_paths

Revision ID: 013_space_learning_path_edges
Revises: 012_space_learning_paths
Create Date: 2026-08-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "013_space_learning_path_edges"
down_revision: Union[str, None] = "012_space_learning_paths"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "space_learning_paths",
        sa.Column(
            "edges",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_column("space_learning_paths", "edges")
