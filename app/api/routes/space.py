from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.space import SpaceModuleCompletion, SpaceProgressResponse
from app.services import space as space_service

router = APIRouter(prefix="/space", tags=["space"])


@router.get(
    "/progress",
    response_model=SpaceProgressResponse,
    summary="List completed Space modules for the current user",
)
def get_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpaceProgressResponse:
    return space_service.list_completed_modules(db, current_user.id)


@router.put(
    "/courses/{course_id}/modules/{module_id}/complete",
    response_model=SpaceModuleCompletion,
    summary="Mark a Space module as completed",
)
def complete_module(
    course_id: str,
    module_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SpaceModuleCompletion:
    return space_service.complete_module(db, current_user.id, course_id, module_id)
