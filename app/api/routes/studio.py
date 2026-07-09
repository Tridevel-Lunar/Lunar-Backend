from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.studio import (
    BranchMapResponse,
    CollectionEntry,
    CollectionListResponse,
    ConversationResponse,
    CreateCollectionRequest,
    SelectBranchRequest,
    UpdateCollectionRequest,
)
from app.services import studio as studio_service

router = APIRouter(prefix="/studio", tags=["studio"])


@router.get(
    "/collections",
    response_model=CollectionListResponse,
    summary="List Studio collections (summary)",
)
def list_studio_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionListResponse:
    items = studio_service.list_collections(db, current_user)
    return CollectionListResponse(items=items)


@router.post(
    "/collections",
    response_model=CollectionEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Create a Studio collection",
)
def create_studio_collection(
    payload: CreateCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionEntry:
    return studio_service.create_collection(db, current_user, payload)


@router.get(
    "/collections/{collection_id}",
    response_model=CollectionEntry,
    summary="Get a Studio collection with conversation tree",
)
def get_studio_collection(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionEntry:
    entry = studio_service.get_collection_entry(db, current_user, collection_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return entry


@router.patch(
    "/collections/{collection_id}",
    response_model=CollectionEntry,
    summary="Update a Studio collection",
)
def update_studio_collection(
    collection_id: UUID,
    payload: UpdateCollectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CollectionEntry:
    entry = studio_service.update_collection(db, current_user, collection_id, payload)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return entry


@router.get(
    "/collections/{collection_id}/conversation",
    response_model=ConversationResponse,
    summary="Get active-branch conversation (path messages only)",
)
def get_studio_conversation(
    collection_id: UUID,
    at: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = studio_service.get_conversation(db, current_user, collection_id, at)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return conversation


@router.post(
    "/collections/{collection_id}/select-branch",
    response_model=ConversationResponse,
    summary="Switch active branch and return its conversation",
)
def select_studio_branch(
    collection_id: UUID,
    payload: SelectBranchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationResponse:
    conversation = studio_service.select_branch(db, current_user, collection_id, payload)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection or branch not found")
    return conversation


@router.get(
    "/collections/{collection_id}/branch-map",
    response_model=BranchMapResponse,
    summary="Branch map graph (user nodes and edges, no full message bodies)",
)
def get_studio_branch_map(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BranchMapResponse:
    branch_map = studio_service.get_branch_map(db, current_user, collection_id)
    if not branch_map:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return branch_map


@router.delete(
    "/collections/{collection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Studio collection",
)
def delete_studio_collection(
    collection_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not studio_service.delete_collection(db, current_user, collection_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
