"""RQ worker task — must be importable at module level."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.arena.engine import execute_run
from app.db.session import SessionLocal


def run_mission_task(user_id: str, mission_id: str, ast: dict[str, Any]) -> dict[str, Any]:
    db = SessionLocal()
    try:
        result = execute_run(
            mission_id=mission_id,
            ast=ast,
            user_id=UUID(user_id),
            db=db,
        )
        return result.model_dump(mode="json")
    finally:
        db.close()
