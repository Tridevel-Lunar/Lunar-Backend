from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PathStep(BaseModel):
    courseId: str
    note: str | None = None


class PathEdge(BaseModel):
    """Directed map edge between catalog course ids (JSON keys: from, to)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)

    from_: str = Field(alias="from")
    to: str


class PathChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class PathProposal(BaseModel):
    intentTags: list[str] = Field(default_factory=list)
    steps: list[PathStep] = Field(default_factory=list)
    edges: list[PathEdge] = Field(default_factory=list)
    final: bool = False


class LearningPathResponse(BaseModel):
    status: Literal["none", "skipped", "active"]
    intentText: str | None = None
    intentTags: list[str] = Field(default_factory=list)
    steps: list[PathStep] = Field(default_factory=list)
    edges: list[PathEdge] = Field(default_factory=list)
    chatTranscript: list[PathChatMessage] = Field(default_factory=list)
    generatedBy: Literal["laika", "skipped"] | None = None
    skippedAt: datetime | None = None
    updatedAt: datetime | None = None


class LearningPathWrite(BaseModel):
    status: Literal["skipped", "active"]
    intentText: str | None = Field(default=None, max_length=8000)
    intentTags: list[str] = Field(default_factory=list)
    steps: list[PathStep] = Field(default_factory=list)
    edges: list[PathEdge] = Field(default_factory=list)
    chatTranscript: list[PathChatMessage] = Field(default_factory=list)


class PathStreamRequest(BaseModel):
    content: str = Field(min_length=0, max_length=8000)
    messages: list[PathChatMessage] = Field(default_factory=list)
    client_now: str | None = None
