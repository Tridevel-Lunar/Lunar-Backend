from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.arena import (
    AttemptResponse,
    MissionPackResponse,
    RunJobResponse,
    RunJobStatusResponse,
    RunRequest,
    SaveAttemptRequest,
)
from app.services import arena as arena_service
from app.services.arena import AstValidationError

router = APIRouter(prefix="/arena", tags=["arena"])


@router.get(
    "/missions/{mission_id}",
    response_model=MissionPackResponse,
    summary="Get Arena mission pack metadata",
)
def get_mission(
    mission_id: str,
    current_user: User = Depends(get_current_user),
) -> MissionPackResponse:
    _ = current_user
    pack = arena_service.get_mission(mission_id)
    if not pack:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return pack


@router.get(
    "/missions/{mission_id}/attempt",
    response_model=AttemptResponse,
    summary="Load draft attempt AST",
)
def get_attempt(
    mission_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttemptResponse:
    attempt = arena_service.get_attempt(db, current_user.id, mission_id)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return attempt


@router.put(
    "/missions/{mission_id}/attempt",
    response_model=AttemptResponse,
    summary="Save draft attempt AST",
)
def save_attempt(
    mission_id: str,
    payload: SaveAttemptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttemptResponse:
    attempt = arena_service.save_attempt(db, current_user.id, mission_id, payload)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return attempt


@router.post(
    "/missions/{mission_id}/runs",
    response_model=RunJobResponse,
    summary="Enqueue mission AST simulation",
)
def submit_run(
    mission_id: str,
    payload: RunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunJobResponse:
    try:
        job, err = arena_service.submit_run(db, current_user.id, mission_id, payload)
    except AstValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.message,
        ) from exc

    if err == "not_found" or job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return job


@router.get(
    "/missions/{mission_id}/runs/{job_id}",
    response_model=RunJobStatusResponse,
    summary="Poll mission run job status",
)
def get_run_job(
    mission_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> RunJobStatusResponse:
    job_status, err = arena_service.get_run_job(current_user.id, mission_id, job_id)
    if err == "not_found" or job_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if err == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return job_status
