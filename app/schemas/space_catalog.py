from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class CatalogOutlineItem(BaseModel):
    id: str
    title: str
    summary: str


class CatalogCourse(BaseModel):
    kind: Literal["course"] = "course"
    id: str
    title: str
    titleTh: str
    summary: str
    status: Literal["published", "coming_soon", "later"]
    level: str = "intro"
    tags: list[str] = Field(default_factory=list)
    teaches: list[str] = Field(default_factory=list)
    audience: str = ""
    intentHints: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    relatedCourseIds: list[str] = Field(default_factory=list)
    recommendWhen: list[str] = Field(default_factory=list)
    doNotConfuseWith: list[str] = Field(default_factory=list)
    arenaHooks: list[str] = Field(default_factory=list)
    outline: list[CatalogOutlineItem] | None = None


class CatalogFolder(BaseModel):
    kind: Literal["folder"] = "folder"
    id: str
    title: str
    titleTh: str
    summary: str
    children: list[Annotated["CatalogNode", Field(discriminator="kind")]]


CatalogNode = Annotated[CatalogFolder | CatalogCourse, Field(discriminator="kind")]

# Rebuild forward refs for recursive folder children
CatalogFolder.model_rebuild()


class SpaceCatalogResponse(BaseModel):
    domainId: str
    title: str
    titleTh: str
    summary: str
    nodes: list[CatalogNode]


class CatalogDigestItem(BaseModel):
    id: str
    title: str
    titleTh: str
    summary: str
    status: Literal["published", "coming_soon", "later"]
    level: str
    path: list[str]
    pathTitles: list[str]
    teaches: list[str]
    audience: str
    intentHints: list[str]
    prerequisites: list[str]
    relatedCourseIds: list[str]
    recommendWhen: list[str]
    doNotConfuseWith: list[str]
    arenaHooks: list[str]
    outline: list[CatalogOutlineItem] | None = None
    tags: list[str] = Field(default_factory=list)


class SpaceCatalogDigestResponse(BaseModel):
    domainId: str
    courses: list[CatalogDigestItem]
    markdown: str
