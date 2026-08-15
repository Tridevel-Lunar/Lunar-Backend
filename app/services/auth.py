from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, RegisterRequest, UpdateMeRequest, UserRead
from app.services.avatars import (
    delete_avatar_files,
    download_and_store_avatar,
    is_external_picture_url,
    is_local_avatar_url,
    store_upload,
)
from app.services.rbac import ROLE_LEARNER, apply_admin_bootstrap


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: UUID) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_google_sub(db: Session, google_sub: str) -> User | None:
    return db.query(User).filter(User.google_sub == google_sub).first()


def user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        picture=user.picture,
        role=user.role,
        created_at=user.created_at,
        google_linked=user.google_sub is not None,
        has_password=bool(user.hashed_password),
    )


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
        role=ROLE_LEARNER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return apply_admin_bootstrap(db, user)


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
    return apply_admin_bootstrap(db, user)


def issue_token_for_user(user: User) -> str:
    return create_access_token(user.id)


def _maybe_localize_picture(db: Session, user: User, remote_picture: str | None) -> User:
    """Download remote Google picture when local avatar is missing or still external."""
    needs = False
    if remote_picture and is_external_picture_url(remote_picture):
        if not user.picture or is_external_picture_url(user.picture):
            needs = True
    if not needs:
        return user

    local = download_and_store_avatar(user.id, remote_picture)
    if local:
        user.picture = local
        db.commit()
        db.refresh(user)
    elif is_external_picture_url(user.picture):
        # Avoid persisting hotlinked Google URLs when download fails.
        user.picture = None
        db.commit()
        db.refresh(user)
    return user


def get_or_create_google_user(
    db: Session,
    *,
    google_sub: str,
    email: str,
    picture: str | None = None,
) -> User:
    """Upsert Google account. Never copies Google display name into Lunar profile."""
    user = get_user_by_google_sub(db, google_sub)
    if user:
        return apply_admin_bootstrap(db, _maybe_localize_picture(db, user, picture))

    normalized_email = email.lower()
    existing = get_user_by_email(db, normalized_email)
    if existing:
        if existing.google_sub and existing.google_sub != google_sub:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already linked to another account",
            )
        existing.google_sub = google_sub
        db.commit()
        db.refresh(existing)
        return apply_admin_bootstrap(db, _maybe_localize_picture(db, existing, picture))

    user = User(
        email=normalized_email,
        google_sub=google_sub,
        display_name=None,
        picture=None,
        hashed_password=None,
        role=ROLE_LEARNER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return apply_admin_bootstrap(db, _maybe_localize_picture(db, user, picture))


def update_me(db: Session, user: User, payload: UpdateMeRequest) -> User:
    if payload.display_name is not None:
        name = payload.display_name.strip()
        user.display_name = name or None
        db.commit()
        db.refresh(user)
    return user


def change_password(db: Session, user: User, payload: ChangePasswordRequest) -> User:
    if user.hashed_password:
        if not payload.current_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is required",
            )
        if not verify_password(payload.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user


def update_my_picture(db: Session, user: User, file_bytes: bytes, content_type: str | None) -> User:
    try:
        public_path = store_upload(user.id, file_bytes, content_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user.picture = public_path
    db.commit()
    db.refresh(user)
    return user


def delete_my_picture(db: Session, user: User) -> User:
    delete_avatar_files(user.id)
    user.picture = None
    db.commit()
    db.refresh(user)
    return user


def link_google_account(
    db: Session,
    user: User,
    *,
    google_sub: str,
    email: str,
    picture: str | None = None,
) -> User:
    """Attach Google identity to the current user. Does not change display_name."""
    if user.google_sub and user.google_sub != google_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already linked to another Google identity",
        )

    other = get_user_by_google_sub(db, google_sub)
    if other and other.id != user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Google account already linked to another user",
        )

    normalized = email.lower()
    if normalized != user.email.lower():
        conflict = get_user_by_email(db, normalized)
        if conflict and conflict.id != user.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Google email belongs to another account",
            )

    user.google_sub = google_sub
    db.commit()
    db.refresh(user)
    if not is_local_avatar_url(user.picture):
        user = _maybe_localize_picture(db, user, picture)
    return user


def unlink_google_account(db: Session, user: User) -> User:
    if not user.google_sub:
        return user
    if not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set a password before unlinking Google",
        )
    user.google_sub = None
    db.commit()
    db.refresh(user)
    return user
