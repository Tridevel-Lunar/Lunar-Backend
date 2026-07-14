from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EntryType = Literal["note", "idea", "learn"]


class CreateCollectionRequest(BaseModel):
    type: EntryType
    content: str = Field(min_length=1, max_length=8000)


class UpdateCollectionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=8000)
    tree: dict[str, Any]
    laika_intent: str | None = Field(default=None, max_length=32)


class CollectionSummary(BaseModel):
    id: UUID
    type: EntryType
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    has_laika: bool


class CollectionEntry(BaseModel):
    id: UUID
    type: EntryType
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    tree: dict[str, Any]
    laika_intent: str | None = None


class CollectionListResponse(BaseModel):
    items: list[CollectionSummary]


class ConversationMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    updated_at: str = ""
    parent_id: str | None = None
    laika_intent: str | None = None


class UserSpot(BaseModel):
    user_node_id: str
    sibling_index: int
    sibling_count: int
    sibling_ids: list[str]
    can_create_branch: bool


class ConversationResponse(BaseModel):
    collection_id: UUID
    type: EntryType
    title: str
    content: str
    laika_intent: str | None = None
    created_at: datetime
    updated_at: datetime
    at_user_node_id: str
    messages: list[ConversationMessage]
    user_spots: list[UserSpot]
    has_laika: bool


class SelectBranchRequest(BaseModel):
    user_node_id: str = Field(min_length=1, max_length=64)


class BranchMapUserNode(BaseModel):
    id: str
    label: str
    created_at: str
    updated_at: str = ""


class BranchMapEdge(BaseModel):
    from_id: str
    to_id: str


class BranchMapResponse(BaseModel):
    collection_id: UUID
    user_nodes: list[BranchMapUserNode]
    edges: list[BranchMapEdge]
    active_user_node_ids: list[str]
    active_edge_keys: list[str]
