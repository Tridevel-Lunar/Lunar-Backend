from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import RegisterRequest


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_google_sub(db: Session, google_sub: str) -> User | None:
    return db.query(User).filter(User.google_sub == google_sub).first()


def register_user(db: Session, payload: RegisterRequest) -> User:
    if get_user_by_email(db, payload.email.lower()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email.lower())
    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return user


def issue_token_for_user(user: User) -> str:
    return create_access_token(user.id)


def get_or_create_google_user(
    db: Session,
    *,
    google_sub: str,
    email: str,
    display_name: str | None,
) -> User:
    user = get_user_by_google_sub(db, google_sub)
    if user:
        if display_name and not user.display_name:
            user.display_name = display_name
            db.commit()
            db.refresh(user)
        return user

    normalized_email = email.lower()
    existing = get_user_by_email(db, normalized_email)
    if existing:
        if existing.google_sub and existing.google_sub != google_sub:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already linked to another account",
            )
        existing.google_sub = google_sub
        if display_name and not existing.display_name:
            existing.display_name = display_name
        db.commit()
        db.refresh(existing)
        return existing

    user = User(
        email=normalized_email,
        google_sub=google_sub,
        display_name=display_name,
        hashed_password=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
