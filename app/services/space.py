from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.space_module_progress import SpaceModuleProgress
from app.schemas.space import SpaceModuleCompletion, SpaceProgressResponse


def list_completed_modules(db: Session, user_id: UUID) -> SpaceProgressResponse:
    rows = (
        db.query(SpaceModuleProgress)
        .filter(SpaceModuleProgress.user_id == user_id)
        .order_by(SpaceModuleProgress.completed_at.asc())
        .all()
    )
    return SpaceProgressResponse(
        completed=[
            SpaceModuleCompletion(
                course_id=row.course_id,
                module_id=row.module_id,
                completed_at=row.completed_at,
            )
            for row in rows
        ]
    )


def complete_module(
    db: Session,
    user_id: UUID,
    course_id: str,
    module_id: str,
) -> SpaceModuleCompletion:
    row = (
        db.query(SpaceModuleProgress)
        .filter(
            SpaceModuleProgress.user_id == user_id,
            SpaceModuleProgress.course_id == course_id,
            SpaceModuleProgress.module_id == module_id,
        )
        .one_or_none()
    )
    if row is None:
        row = SpaceModuleProgress(
            user_id=user_id,
            course_id=course_id,
            module_id=module_id,
            completed_at=datetime.now(UTC),
        )
        db.add(row)
    else:
        row.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return SpaceModuleCompletion(
        course_id=row.course_id,
        module_id=row.module_id,
        completed_at=row.completed_at,
    )
