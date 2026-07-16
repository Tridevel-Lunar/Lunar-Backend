from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.arena import AttemptResponse, MissionPackResponse, SaveAttemptRequest
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
    current_user: User = Depends(get_current_user),
) -> AttemptResponse:
    attempt = arena_service.get_attempt(current_user.id, mission_id)
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
) -> AttemptResponse:
    attempt = arena_service.save_attempt(current_user.id, mission_id, payload)
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return attempt
