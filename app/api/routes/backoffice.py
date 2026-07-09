import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_backoffice_user, get_current_user
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.backoffice import (
    BackofficeAccessResponse,
    BackofficeUserItem,
    BackofficeUsersResponse,
    IngestRequest,
    IngestResponse,
    IngestSourceResultItem,
    KnowledgeCatalogItemSchema,
    KnowledgeCatalogResponse,
    KnowledgeModuleGroupSchema,
    KnowledgeOverviewResponse,
    KnowledgeSourceDetailResponse,
    KnowledgeSourceItem,
    SyncManifestRequest,
    UpdateKnowledgeSourceRequest,
    UpdateKnowledgeSourceResponse,
    UpdateUserRoleRequest,
    UploadKnowledgeResponse,
)
from app.services.knowledge.ingest import (
    delete_knowledge_source,
    get_knowledge_catalog,
    get_knowledge_overview,
    get_knowledge_source_detail,
    ingest_knowledge,
    sync_manifest_sources,
    update_knowledge_source,
    upload_and_ingest,
)
from app.services.rbac import is_admin
from app.services.user_admin import count_admins, list_users, update_user_role

router = APIRouter(prefix="/backoffice", tags=["backoffice"])


@router.get(
    "/access",
    response_model=BackofficeAccessResponse,
    summary="Check backoffice access for current user",
)
def backoffice_access(
    current_user: User = Depends(get_current_user),
) -> BackofficeAccessResponse:
    return BackofficeAccessResponse(
        allowed=is_admin(current_user),
        role=current_user.role,
    )


@router.get(
    "/users",
    response_model=BackofficeUsersResponse,
    summary="List all users",
)
def users_list(
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
) -> BackofficeUsersResponse:
    users = list_users(db)
    return BackofficeUsersResponse(
        users=[
            BackofficeUserItem(
                id=str(u.id),
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                created_at=u.created_at,
            )
            for u in users
        ],
        admin_count=count_admins(db),
    )


@router.patch(
    "/users/{user_id}",
    response_model=BackofficeUserItem,
    summary="Update a user's role",
)
def users_update_role(
    user_id: str,
    body: UpdateUserRoleRequest,
    acting_user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
) -> BackofficeUserItem:
    try:
        parsed_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user id",
        ) from exc

    updated = update_user_role(
        db,
        user_id=parsed_id,
        role=body.role,  # type: ignore[arg-type]
        acting_user=acting_user,
    )
    return BackofficeUserItem(
        id=str(updated.id),
        email=updated.email,
        display_name=updated.display_name,
        role=updated.role,
        created_at=updated.created_at,
    )


@router.get(
    "/knowledge/catalog",
    response_model=KnowledgeCatalogResponse,
    summary="Manifest catalog grouped by module with sync status",
)
def knowledge_catalog(
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> KnowledgeCatalogResponse:
    catalog = get_knowledge_catalog(db, settings)
    return KnowledgeCatalogResponse(
        total_chunks=catalog.total_chunks,
        embedding_provider=catalog.embedding_provider,
        embedding_enabled=catalog.embedding_enabled,
        modules=[
            KnowledgeModuleGroupSchema(
                module=group.module,
                sources=[
                    KnowledgeCatalogItemSchema(
                        manifest_id=item.manifest_id,
                        title=item.title,
                        module=item.module,
                        stage=item.stage,
                        order=item.order,
                        path=item.path,
                        type=item.type,
                        language=item.language,
                        topic=item.topic,
                        synced=item.synced,
                        id=item.id,
                        filename=item.filename,
                        chunk_count=item.chunk_count,
                        last_ingested_at=item.last_ingested_at,
                        created_at=item.created_at,
                    )
                    for item in group.sources
                ],
            )
            for group in catalog.modules
        ],
        uploads=[
            KnowledgeSourceItem(
                id=source.id,
                manifest_id=source.manifest_id,
                title=source.title,
                filename=source.filename,
                type=source.type,
                module=source.module,
                stage=source.stage,
                source_origin=source.source_origin,
                language=source.language,
                topic=source.topic,
                license=source.license,
                chunk_count=source.chunk_count,
                last_ingested_at=source.last_ingested_at,
                created_at=source.created_at,
            )
            for source in catalog.uploads
        ],
    )


@router.get(
    "/knowledge/sources/{source_id}",
    response_model=KnowledgeSourceDetailResponse,
    summary="Get knowledge source detail and editable content",
)
def knowledge_source_detail(
    source_id: str,
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
) -> KnowledgeSourceDetailResponse:
    try:
        detail = get_knowledge_source_detail(db, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return KnowledgeSourceDetailResponse(
        id=detail.id,
        manifest_id=detail.manifest_id,
        title=detail.title,
        filename=detail.filename,
        type=detail.type,
        module=detail.module,
        stage=detail.stage,
        source_origin=detail.source_origin,
        language=detail.language,
        topic=detail.topic,
        license=detail.license,
        content=detail.content,
        content_editable=detail.content_editable,
        chunk_count=detail.chunk_count,
        last_ingested_at=detail.last_ingested_at,
    )


@router.patch(
    "/knowledge/sources/{source_id}",
    response_model=UpdateKnowledgeSourceResponse,
    summary="Update knowledge source metadata and content",
)
def knowledge_source_update(
    source_id: str,
    payload: UpdateKnowledgeSourceRequest,
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UpdateKnowledgeSourceResponse:
    try:
        result = update_knowledge_source(
            db,
            settings,
            source_id,
            title=payload.title,
            topic=payload.topic,
            language=payload.language,
            license_value=payload.license,
            content=payload.content,
            auto_reingest=payload.auto_reingest,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "Embedding provider" in str(exc)
            else status.HTTP_400_BAD_REQUEST
            if "Content can only" in str(exc)
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return UpdateKnowledgeSourceResponse(
        id=result.id,
        title=result.title,
        chunks_ingested=result.chunks_ingested,
    )


@router.get(
    "/knowledge",
    response_model=KnowledgeOverviewResponse,
    summary="Knowledge corpus overview",
)
def knowledge_overview(
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> KnowledgeOverviewResponse:
    overview = get_knowledge_overview(db, settings)
    return KnowledgeOverviewResponse(
        total_chunks=overview.total_chunks,
        embedding_provider=overview.embedding_provider,
        embedding_enabled=overview.embedding_enabled,
        sources=[
            KnowledgeSourceItem(
                id=source.id,
                manifest_id=source.manifest_id,
                title=source.title,
                filename=source.filename,
                type=source.type,
                module=source.module,
                stage=source.stage,
                source_origin=source.source_origin,
                language=source.language,
                topic=source.topic,
                license=source.license,
                chunk_count=source.chunk_count,
                last_ingested_at=source.last_ingested_at,
                created_at=source.created_at,
            )
            for source in overview.sources
        ],
    )


@router.post(
    "/knowledge/upload",
    response_model=UploadKnowledgeResponse,
    summary="Upload a knowledge document and ingest into pgvector",
    responses={
        400: {"description": "Invalid file"},
        503: {"description": "Embedding provider not configured"},
    },
)
async def knowledge_upload(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    topic: str | None = Form(default=None),
    language: str = Form(default="th"),
    license_value: str | None = Form(default=None),
    auto_ingest: bool = Form(default=True),
    user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadKnowledgeResponse:
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing filename")

    file_data = await file.read()
    if not file_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")

    try:
        result = upload_and_ingest(
            db,
            settings,
            filename=file.filename,
            file_data=file_data,
            title=title,
            topic=topic,
            language=language,
            license_value=license_value,
            uploaded_by=user.id,
            auto_ingest=auto_ingest,
        )
    except ValueError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "Embedding provider" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return UploadKnowledgeResponse(
        source_id=result.source_id,
        title=result.title,
        filename=result.filename,
        source_type=result.source_type,
        chunks_ingested=result.chunks_ingested,
    )


@router.post(
    "/knowledge/ingest",
    response_model=IngestResponse,
    summary="Re-ingest uploaded knowledge sources into pgvector",
    responses={
        503: {"description": "Embedding provider not configured"},
    },
)
def knowledge_ingest(
    payload: IngestRequest,
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    try:
        result = ingest_knowledge(db, settings, source_id=payload.source_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    return IngestResponse(
        total_chunks=result.total_chunks,
        results=[
            IngestSourceResultItem(
                source_id=item.source_id,
                chunks_ingested=item.chunks_ingested,
            )
            for item in result.results
        ],
    )


@router.post(
    "/knowledge/sync-manifest",
    response_model=IngestResponse,
    summary="Sync manifest.yaml sources into database and ingest",
    responses={
        404: {"description": "Manifest file or entry not found"},
        503: {"description": "Embedding provider not configured"},
    },
)
def knowledge_sync_manifest(
    payload: SyncManifestRequest,
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    try:
        result = sync_manifest_sources(db, settings, source_id=payload.source_id)
    except ValueError as exc:
        status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if "Embedding provider" in str(exc)
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return IngestResponse(
        total_chunks=result.total_chunks,
        results=[
            IngestSourceResultItem(
                source_id=item.source_id,
                chunks_ingested=item.chunks_ingested,
            )
            for item in result.results
        ],
    )


@router.delete(
    "/knowledge/sources/{source_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded knowledge source and its chunks",
)
def knowledge_delete_source(
    source_id: str,
    _user: User = Depends(get_backoffice_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_knowledge_source(db, source_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
