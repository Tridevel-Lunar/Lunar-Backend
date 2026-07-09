"""knowledge source manifest metadata

Revision ID: 004_knowledge_source_manifest
Revises: 003_knowledge_sources
Create Date: 2026-07-07

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_knowledge_source_manifest"
down_revision: Union[str, None] = "003_knowledge_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("manifest_id", sa.String(length=128), nullable=True))
    op.add_column("knowledge_sources", sa.Column("module", sa.String(length=32), nullable=True))
    op.add_column("knowledge_sources", sa.Column("stage", sa.String(length=128), nullable=True))
    op.add_column(
        "knowledge_sources",
        sa.Column("source_origin", sa.String(length=16), nullable=False, server_default="upload"),
    )
    op.create_index("ix_knowledge_sources_manifest_id", "knowledge_sources", ["manifest_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_knowledge_sources_manifest_id", table_name="knowledge_sources")
    op.drop_column("knowledge_sources", "source_origin")
    op.drop_column("knowledge_sources", "stage")
    op.drop_column("knowledge_sources", "module")
    op.drop_column("knowledge_sources", "manifest_id")
