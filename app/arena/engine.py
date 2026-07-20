"""Pure mission run engine — no HTTP or RQ."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arena.ast.validator import validate_ast
from app.arena.interpreter import interpret
from app.arena.missions import get_mission_pack
from app.models.arena_attempt import ArenaAttempt
from app.schemas.arena import RunResult


class MissionNotFoundError(Exception):
    pass


def _get_row(db: Session, user_id: UUID, mission_id: str) -> ArenaAttempt | None:
    return db.scalar(
        select(ArenaAttempt).where(
            ArenaAttempt.user_id == user_id,
            ArenaAttempt.mission_id == mission_id,
        )
    )


def _persist_attempt(
    db: Session,
    user_id: UUID,
    mission_id: str,
    ast: dict[str, Any],
    result: RunResult,
) -> None:
    now = datetime.now(UTC)
    row = _get_row(db, user_id, mission_id)
    result_dict = result.model_dump(mode="json")
    if row is None:
        row = ArenaAttempt(
            user_id=user_id,
            mission_id=mission_id,
            ast=ast,
            last_result=result_dict,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.ast = ast
        row.last_result = result_dict
        row.updated_at = now
    db.commit()


def execute_run(
    *,
    mission_id: str,
    ast: dict[str, Any],
    user_id: UUID,
    db: Session,
) -> RunResult:
    pack = get_mission_pack(mission_id)
    if pack is None:
        raise MissionNotFoundError(mission_id)

    validate_ast(
        ast,
        allowed_ops=list(pack["allowedOps"]),
        limits=dict(pack["limits"]),
    )

    raw = interpret(ast, mission_id=mission_id, pack=pack)
    result = RunResult.model_validate(raw)
    _persist_attempt(db, user_id, mission_id, ast, result)
    return result
