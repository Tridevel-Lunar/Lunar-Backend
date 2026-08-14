from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.space import SpaceModuleCompletion, SpaceProgressResponse
from app.schemas.space_catalog import SpaceCatalogDigestResponse, SpaceCatalogResponse
from app.services import space as space_service
from app.services import space_catalog as space_catalog_service

router = APIRouter(prefix="/space", tags=["space"])


@router.get(
    "/catalog",
    response_model=SpaceCatalogResponse,
    summary="Space Technology catalog tree (folders + course leaves)",
)
def get_catalog(
    current_user: User = Depends(get_current_user),
) -> SpaceCatalogResponse:
    _ = current_user
    return space_catalog_service.get_catalog_tree()


@router.get(
    "/catalog/digest",
    response_model=SpaceCatalogDigestResponse,
    summary="Flat catalog digest for LAIKA / debugging",
)
def get_catalog_digest(
    current_user: User = Depends(get_current_user),
    include_later: bool = Query(
        False,
        description="Include status=later courses in the digest",
    ),
) -> SpaceCatalogDigestResponse:
    _ = current_user
    return space_catalog_service.get_catalog_digest(include_later=include_later)


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
