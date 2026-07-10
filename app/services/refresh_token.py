import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth import get_user_by_id


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _generate_plain_token() -> str:
    return secrets.token_urlsafe(32)


def create_refresh_token(db: Session, user_id: UUID) -> str:
    settings = get_settings()
    plain = _generate_plain_token()
    record = RefreshToken(
        user_id=user_id,
        token_hash=_hash_token(plain),
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(record)
    db.commit()
    return plain


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _get_valid_record(db: Session, plain: str) -> RefreshToken | None:
    record = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_token(plain)).first()
    )
    if not record:
        return None
    if _as_utc(record.expires_at) <= datetime.now(UTC):
        db.delete(record)
        db.commit()
        return None
    return record


def rotate_refresh_token(db: Session, plain: str) -> tuple[User, str]:
    record = _get_valid_record(db, plain)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = get_user_by_id(db, record.user_id)
    if not user:
        db.delete(record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = record.user_id
    db.delete(record)
    db.flush()

    settings = get_settings()
    new_plain = _generate_plain_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_token(new_plain),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    db.commit()
    return user, new_plain


def revoke_refresh_token(db: Session, plain: str) -> None:
    record = (
        db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_token(plain)).first()
    )
    if record:
        db.delete(record)
        db.commit()
