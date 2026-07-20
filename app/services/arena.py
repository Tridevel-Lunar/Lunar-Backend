"""Arena attempt persistence and mission run orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.arena.ast.validator import AstValidationError, validate_ast
from app.arena.missions import get_mission_pack
from app.arena.queue import enqueue_run, fetch_job_status
from app.models.arena_attempt import ArenaAttempt
from app.schemas.arena import (
    AttemptResponse,
    MissionPackResponse,
    RunJobResponse,
    RunJobStatusResponse,
    RunRequest,
    RunResult,
    SaveAttemptRequest,
)


def get_mission(mission_id: str) -> MissionPackResponse | None:
    pack = get_mission_pack(mission_id)
    if not pack:
        return None
    return MissionPackResponse(
        id=pack["id"],
        toolboxId=pack["toolboxId"],
        title=pack["title"],
        code=pack["code"],
        level=pack["level"],
        playable=pack["playable"],
        allowedOps=list(pack["allowedOps"]),
        limits=pack["limits"],
    )


def _row_to_attempt(row: ArenaAttempt | None, mission_id: str) -> AttemptResponse:
    if row is None:
        return AttemptResponse(mission_id=mission_id, ast=None, last_result=None)
    last: RunResult | None = None
    if row.last_result is not None:
        last = RunResult.model_validate(row.last_result)
    return AttemptResponse(mission_id=mission_id, ast=row.ast, last_result=last)


def _get_row(db: Session, user_id: UUID, mission_id: str) -> ArenaAttempt | None:
    return db.scalar(
        select(ArenaAttempt).where(
            ArenaAttempt.user_id == user_id,
            ArenaAttempt.mission_id == mission_id,
        )
    )


def get_attempt(db: Session, user_id: UUID, mission_id: str) -> AttemptResponse | None:
    if get_mission_pack(mission_id) is None:
        return None
    row = _get_row(db, user_id, mission_id)
    return _row_to_attempt(row, mission_id)


def save_attempt(
    db: Session,
    user_id: UUID,
    mission_id: str,
    payload: SaveAttemptRequest,
) -> AttemptResponse | None:
    if get_mission_pack(mission_id) is None:
        return None

    now = datetime.now(UTC)
    row = _get_row(db, user_id, mission_id)
    if row is None:
        row = ArenaAttempt(
            user_id=user_id,
            mission_id=mission_id,
            ast=payload.ast,
            last_result=None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.ast = payload.ast
        row.updated_at = now

    db.commit()
    db.refresh(row)
    return _row_to_attempt(row, mission_id)


def submit_run(
    db: Session,
    user_id: UUID,
    mission_id: str,
    payload: RunRequest,
) -> tuple[RunJobResponse | None, str | None]:
    """
    Validate AST and enqueue a run job.

    Returns (job, error_code) where error_code is None or "not_found".
  """
    _ = db
    pack = get_mission_pack(mission_id)
    if pack is None:
        return None, "not_found"

    validate_ast(
        payload.ast,
        allowed_ops=list(pack["allowedOps"]),
        limits=dict(pack["limits"]),
    )

    job_id = enqueue_run(db, user_id, mission_id, payload.ast)
    return (
        RunJobResponse(job_id=job_id, status="pending", mission_id=mission_id),
        None,
    )


def get_run_job(
    user_id: UUID,
    mission_id: str,
    job_id: str,
) -> tuple[RunJobStatusResponse | None, str | None]:
    """
    Fetch job status.

    Returns (status, error_code) where error_code is None, "not_found", or "forbidden".
    """
    if get_mission_pack(mission_id) is None:
        return None, "not_found"

    status = fetch_job_status(user_id=user_id, mission_id=mission_id, job_id=job_id)
    if status is None:
        return None, "not_found"
    return status, None


__all__ = [
    "AstValidationError",
    "get_attempt",
    "get_mission",
    "get_run_job",
    "save_attempt",
    "submit_run",
]
