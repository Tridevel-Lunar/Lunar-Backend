from datetime import datetime

from pydantic import BaseModel, Field


class BackofficeAccessResponse(BaseModel):
    allowed: bool
    role: str


class KnowledgeSourceItem(BaseModel):
    id: str
    manifest_id: str | None
    title: str
    filename: str
    type: str
    module: str | None
    stage: str | None
    source_origin: str
    language: str
    topic: str | None
    license: str | None
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime


class KnowledgeOverviewResponse(BaseModel):
    total_chunks: int
    embedding_provider: str
    embedding_enabled: bool
    sources: list[KnowledgeSourceItem]


class IngestRequest(BaseModel):
    source_id: str = Field(default="all", description="Source id, manifest id, or 'all'")


class SyncManifestRequest(BaseModel):
    source_id: str = Field(default="all", description="Manifest source id or 'all'")


class IngestSourceResultItem(BaseModel):
    source_id: str
    chunks_ingested: int


class IngestResponse(BaseModel):
    total_chunks: int
    results: list[IngestSourceResultItem]


class UploadKnowledgeResponse(BaseModel):
    source_id: str
    title: str
    filename: str
    source_type: str
    chunks_ingested: int


class BackofficeUserItem(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: str
    created_at: datetime


class BackofficeUsersResponse(BaseModel):
    users: list[BackofficeUserItem]
    admin_count: int


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(description="learner or admin")


class KnowledgeCatalogItemSchema(BaseModel):
    manifest_id: str
    title: str
    module: str
    stage: str | None
    order: int | None
    path: str
    type: str
    language: str
    topic: str | None
    synced: bool
    id: str | None
    filename: str | None
    chunk_count: int
    last_ingested_at: datetime | None
    created_at: datetime | None


class KnowledgeModuleGroupSchema(BaseModel):
    module: str
    sources: list[KnowledgeCatalogItemSchema]


class KnowledgeCatalogResponse(BaseModel):
    total_chunks: int
    embedding_provider: str
    embedding_enabled: bool
    modules: list[KnowledgeModuleGroupSchema]
    uploads: list[KnowledgeSourceItem]


class KnowledgeSourceDetailResponse(BaseModel):
    id: str
    manifest_id: str | None
    title: str
    filename: str
    type: str
    module: str | None
    stage: str | None
    source_origin: str
    language: str
    topic: str | None
    license: str | None
    content: str | None
    content_editable: bool
    chunk_count: int
    last_ingested_at: datetime | None


class UpdateKnowledgeSourceRequest(BaseModel):
    title: str | None = None
    topic: str | None = None
    language: str | None = None
    license: str | None = None
    content: str | None = None
    auto_reingest: bool = True


class UpdateKnowledgeSourceResponse(BaseModel):
    id: str
    title: str
    chunks_ingested: int
