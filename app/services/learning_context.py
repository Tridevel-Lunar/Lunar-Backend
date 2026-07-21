"""Build LAIKA learning_context from Space progress and Arena attempts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.schemas.laika import LearningContext
from app.services import arena as arena_service
from app.services import space as space_service

# Keep in sync with frontend Space course registry.
COURSE_MODULES: dict[str, dict[str, object]] = {
    "cubesat-for-beginner": {
        "title": "CubeSat for Beginner",
        "title_th": "พื้นฐานดาวเทียม",
        "module_order": ["overview", "anatomy", "physics", "programming"],
        "module_labels": {
            "overview": "Overview of Satellite (ภาพรวมดาวเทียม)",
            "anatomy": "Anatomy of CubeSat (โครงสร้าง CubeSat)",
            "physics": "Physics for Space (ฟิสิกส์ในอวกาศ)",
            "programming": "Programming for CubeSat (การเขียนโปรแกรม)",
        },
    },
}

ARENA_MISSIONS: list[tuple[str, str]] = [
    ("leo-orbital-launch", "MISSION 01 — LEO Orbital Launch"),
]

DEFAULT_COURSE_ID = "cubesat-for-beginner"


def _module_label(course_id: str, module_id: str) -> str:
    course = COURSE_MODULES.get(course_id)
    if not isinstance(course, dict):
        return module_id
    labels = course.get("module_labels")
    if isinstance(labels, dict) and module_id in labels:
        return str(labels[module_id])
    return module_id


def _course_title(course_id: str) -> str | None:
    course = COURSE_MODULES.get(course_id)
    if not isinstance(course, dict):
        return None
    title_th = course.get("title_th")
    title = course.get("title")
    if isinstance(title_th, str) and title_th.strip():
        return title_th.strip()
    if isinstance(title, str) and title.strip():
        return title.strip()
    return None


def resolve_learning_context(
    db: Session,
    user_id: UUID,
    *,
    client: LearningContext | None = None,
) -> LearningContext:
    """Merge DB progress with optional client hints (client course only when DB is empty)."""
    progress = space_service.list_completed_modules(db, user_id)

    completed_by_course: dict[str, set[str]] = {}
    for row in progress.completed:
        completed_by_course.setdefault(row.course_id, set()).add(row.module_id)

    if completed_by_course:
        primary_course = max(
            completed_by_course.keys(),
            key=lambda cid: (len(completed_by_course[cid]), 1 if cid in COURSE_MODULES else 0),
        )
    else:
        primary_course = (client.course if client and client.course else None) or DEFAULT_COURSE_ID

    course_meta = COURSE_MODULES.get(primary_course)
    module_order: list[str] = []
    if isinstance(course_meta, dict):
        order = course_meta.get("module_order")
        if isinstance(order, list):
            module_order = [str(m) for m in order]

    completed_set = completed_by_course.get(primary_course, set())
    completed_modules = sorted(
        completed_set,
        key=lambda module_id: module_order.index(module_id) if module_id in module_order else 99,
    )
    pending_modules = [module_id for module_id in module_order if module_id not in completed_set]

    completed_topics = [_module_label(primary_course, module_id) for module_id in completed_modules]
    pending_topics = [_module_label(primary_course, module_id) for module_id in pending_modules]

    percent: int | None = None
    if module_order:
        percent = round(len(completed_modules) / len(module_order) * 100)

    arena_missions: list[str] = []
    for mission_id, title in ARENA_MISSIONS:
        attempt = arena_service.get_attempt(user_id, mission_id)
        if attempt is not None and attempt.ast:
            arena_missions.append(f"{title} — Blockly draft saved")

    return LearningContext(
        course=primary_course,
        course_title=_course_title(primary_course),
        completed_topics=completed_topics,
        completed_modules=completed_modules,
        pending_modules=pending_modules,
        pending_topics=pending_topics,
        space_progress_percent=percent,
        arena_missions=arena_missions,
    )
