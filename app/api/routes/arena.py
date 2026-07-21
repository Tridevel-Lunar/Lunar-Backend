from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.arena import (
    AttemptResponse,
    MissionPackResponse,
    MissionRunResponse,
    RunMissionRequest,
    SaveAttemptRequest,
)
from app.services import arena as arena_service

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttemptResponse:
    attempt = arena_service.save_attempt(db, current_user.id, mission_id, payload)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return attempt


@router.post(
    "/missions/{mission_id}/runs",
    response_model=MissionRunResponse,
    summary="Run deterministic mission simulation",
)
def run_mission(
    mission_id: str,
    payload: RunMissionRequest,
    current_user: User = Depends(get_current_user),
) -> MissionRunResponse:
    try:
        result = arena_service.run_mission(current_user.id, mission_id, payload)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(err)) from err
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return result
