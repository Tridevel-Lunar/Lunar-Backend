"""Load and serve the Space Technology catalog (file-backed source of truth)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from app.schemas.space_catalog import (
    CatalogCourse,
    CatalogDigestItem,
    CatalogFolder,
    CatalogNode,
    SpaceCatalogDigestResponse,
    SpaceCatalogResponse,
)

_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "space" / "catalog.json"
)

_DEFAULT_DIGEST_STATUSES = frozenset({"published", "coming_soon"})


@lru_cache(maxsize=1)
def load_catalog() -> SpaceCatalogResponse:
    raw = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    catalog = SpaceCatalogResponse.model_validate(raw)
    _validate_tree(catalog.nodes)
    return catalog


def get_catalog_tree() -> SpaceCatalogResponse:
    return load_catalog()


def clear_catalog_cache() -> None:
    load_catalog.cache_clear()


def _validate_tree(nodes: list[CatalogNode]) -> None:
    seen_ids: set[str] = set()

    def walk(items: list[CatalogNode]) -> None:
        for node in items:
            if node.id in seen_ids:
                raise ValueError(f"Duplicate catalog id: {node.id}")
            seen_ids.add(node.id)
            if isinstance(node, CatalogFolder):
                if not node.children:
                    raise ValueError(f"Folder {node.id} has no children")
                walk(node.children)
            elif isinstance(node, CatalogCourse):
                if node.status == "published" and node.id == "cubesat-for-beginner":
                    if not node.outline or len(node.outline) < 1:
                        raise ValueError("Pilot course must include outline modules")

    walk(nodes)


def iter_courses(
    nodes: list[CatalogNode] | None = None,
    *,
    path_ids: list[str] | None = None,
    path_titles: list[str] | None = None,
) -> Iterable[CatalogDigestItem]:
    tree = nodes if nodes is not None else get_catalog_tree().nodes
    ids = path_ids or []
    titles = path_titles or []
    for node in tree:
        if isinstance(node, CatalogFolder):
            yield from iter_courses(
                node.children,
                path_ids=[*ids, node.id],
                path_titles=[*titles, node.title],
            )
        else:
            yield CatalogDigestItem(
                id=node.id,
                title=node.title,
                titleTh=node.titleTh,
                summary=node.summary,
                status=node.status,
                level=node.level,
                path=ids,
                pathTitles=titles,
                teaches=list(node.teaches),
                audience=node.audience,
                intentHints=list(node.intentHints),
                prerequisites=list(node.prerequisites),
                relatedCourseIds=list(node.relatedCourseIds),
                recommendWhen=list(node.recommendWhen),
                doNotConfuseWith=list(node.doNotConfuseWith),
                arenaHooks=list(node.arenaHooks),
                outline=node.outline,
                tags=list(node.tags),
            )


def find_course(course_id: str) -> CatalogDigestItem | None:
    for item in iter_courses():
        if item.id == course_id:
            return item
    return None


def format_catalog_digest(
    *,
    statuses: Iterable[str] | None = None,
    max_chars: int | None = 6000,
    include_later: bool = False,
) -> str:
    allowed = (
        frozenset(statuses)
        if statuses is not None
        else (
            frozenset({"published", "coming_soon", "later"})
            if include_later
            else _DEFAULT_DIGEST_STATUSES
        )
    )
    lines = [
        "## Space Technology catalog (authoritative)",
        "Recommend ONLY by course id from this list.",
        "status=published is enterable today; coming_soon may be mentioned as upcoming; later is soft.",
        "Folders are navigation only — never recommend a folder as a lesson.",
        "Lunar is space technology broadly — do not force every intent through cubesat-for-beginner.",
        "",
    ]
    for item in iter_courses():
        if item.status not in allowed:
            continue
        path = " > ".join(item.pathTitles) if item.pathTitles else "(root)"
        lines.append(
            f"- [{item.status}] `{item.id}` · {item.title} · {item.titleTh}"
        )
        lines.append(f"  path: {path}")
        if item.summary:
            lines.append(f"  summary: {item.summary}")
        if item.teaches:
            lines.append(f"  teaches: {', '.join(item.teaches)}")
        if item.intentHints:
            lines.append(f"  intentHints: {', '.join(item.intentHints)}")
        if item.recommendWhen:
            lines.append(f"  recommendWhen: {', '.join(item.recommendWhen)}")
        if item.prerequisites:
            lines.append(f"  prereq: {', '.join(item.prerequisites)}")
        else:
            lines.append("  prereq: (none)")
        if item.doNotConfuseWith:
            lines.append(f"  doNotConfuseWith: {', '.join(item.doNotConfuseWith)}")
        if item.arenaHooks:
            lines.append(f"  arenaHooks: {', '.join(item.arenaHooks)}")
        if item.outline:
            outline_ids = ", ".join(m.id for m in item.outline)
            lines.append(f"  outline: {outline_ids}")
        lines.append("")

    text = "\n".join(lines).rstrip() + "\n"
    if max_chars is not None and len(text) > max_chars:
        truncated = text[: max_chars - 80].rstrip()
        text = (
            truncated
            + "\n\n…(catalog digest truncated; prefer published + coming_soon courses)\n"
        )
    return text


def get_catalog_digest(
    *,
    statuses: Iterable[str] | None = None,
    include_later: bool = False,
) -> SpaceCatalogDigestResponse:
    catalog = get_catalog_tree()
    allowed = (
        frozenset(statuses)
        if statuses is not None
        else (
            frozenset({"published", "coming_soon", "later"})
            if include_later
            else _DEFAULT_DIGEST_STATUSES
        )
    )
    courses = [c for c in iter_courses() if c.status in allowed]
    markdown = format_catalog_digest(statuses=allowed, include_later=include_later)
    return SpaceCatalogDigestResponse(
        domainId=catalog.domainId,
        courses=courses,
        markdown=markdown,
    )
