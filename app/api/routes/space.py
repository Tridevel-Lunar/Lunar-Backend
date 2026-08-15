import threading

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.space import SpaceModuleCompletion, SpaceProgressResponse
from app.schemas.space_catalog import SpaceCatalogDigestResponse, SpaceCatalogResponse
from app.schemas.space_learning_path import (
    LearningPathResponse,
    LearningPathWrite,
    PathStreamRequest,
)
from app.services import space as space_service
from app.services import space_catalog as space_catalog_service
from app.services import space_learning_path as path_service

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


@router.get(
    "/learning-path",
    response_model=LearningPathResponse,
    summary="Current Space learning path (or none/skipped)",
)
def get_learning_path(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningPathResponse:
    return path_service.get_path(db, current_user.id)


@router.put(
    "/learning-path",
    response_model=LearningPathResponse,
    summary="Save a learning path or mark skipped",
)
def put_learning_path(
    payload: LearningPathWrite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningPathResponse:
    return path_service.upsert_path(db, current_user.id, payload)


@router.delete(
    "/learning-path",
    status_code=204,
    summary="Clear learning path so the learner can plan again",
)
def delete_learning_path(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    path_service.delete_path(db, current_user.id)


@router.post(
    "/laika/path/stream",
    summary="LAIKA Space path-building chat (SSE)",
    responses={
        503: {"description": "LAIKA LLM disabled or provider misconfigured"},
    },
)
def space_path_stream(
    payload: PathStreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    cancel = threading.Event()
    return StreamingResponse(
        path_service.iter_path_stream_sse(db, settings, payload, current_user.id, cancel),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
