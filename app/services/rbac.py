from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User

UserRole = Literal["learner", "admin"]

ROLE_LEARNER: UserRole = "learner"
ROLE_ADMIN: UserRole = "admin"


def is_admin(user: User) -> bool:
    return user.role == ROLE_ADMIN


def apply_admin_bootstrap(db: Session, user: User) -> User:
    """Promote user to admin when email is listed in ADMIN_EMAILS (bootstrap only)."""
    settings = get_settings()
    if user.email.lower() in settings.admin_emails_list and user.role != ROLE_ADMIN:
        user.role = ROLE_ADMIN
        db.commit()
        db.refresh(user)
    return user
