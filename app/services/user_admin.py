import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.rbac import ROLE_ADMIN, ROLE_LEARNER, UserRole

VALID_ROLES = {ROLE_LEARNER, ROLE_ADMIN}


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


def count_admins(db: Session) -> int:
    return db.query(User).filter(User.role == ROLE_ADMIN).count()


def update_user_role(
    db: Session,
    *,
    user_id: uuid.UUID,
    role: UserRole,
    acting_user: User,
) -> User:
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if target.id == acting_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    if target.role == ROLE_ADMIN and role == ROLE_LEARNER and count_admins(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote the last admin",
        )

    target.role = role
    db.commit()
    db.refresh(target)
    return target
