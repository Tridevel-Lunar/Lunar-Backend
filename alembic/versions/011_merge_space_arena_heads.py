"""merge space progress and arena attempts migration heads

Revision ID: 011_merge_heads
Revises: 009_space_module_progress, 010_arena_mission_ver
Create Date: 2026-07-21

"""

from typing import Sequence, Union

revision: str = "011_merge_heads"
down_revision: Union[str, tuple[str, ...], None] = (
    "009_space_module_progress",
    "010_arena_mission_ver",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
