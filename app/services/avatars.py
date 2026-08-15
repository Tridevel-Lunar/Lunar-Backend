"""Local avatar file storage and Google image download."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

PUBLIC_AVATAR_PREFIX = "/api/avatars"


def avatars_dir() -> Path:
    settings = get_settings()
    root = Path(settings.avatars_dir)
    if not root.is_absolute():
        # Resolve relative to backend package root (…/backend)
        backend_root = Path(__file__).resolve().parents[2]
        root = backend_root / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def public_avatar_url(user_id: UUID) -> str:
    return f"{PUBLIC_AVATAR_PREFIX}/{user_id}"


def is_external_picture_url(picture: str | None) -> bool:
    if not picture:
        return False
    return picture.startswith("http://") or picture.startswith("https://")


def is_local_avatar_url(picture: str | None) -> bool:
    if not picture:
        return False
    return picture.startswith(f"{PUBLIC_AVATAR_PREFIX}/")


def _ext_for_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    base = content_type.split(";")[0].strip().lower()
    return ALLOWED_CONTENT_TYPES.get(base)


def _clear_existing_files(user_id: UUID) -> None:
    directory = avatars_dir()
    for path in directory.glob(f"{user_id}.*"):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove avatar file %s", path)


def avatar_file_path(user_id: UUID) -> Path | None:
    directory = avatars_dir()
    matches = sorted(directory.glob(f"{user_id}.*"))
    return matches[0] if matches else None


def store_upload(user_id: UUID, file_bytes: bytes, content_type: str | None) -> str:
    if len(file_bytes) == 0:
        raise ValueError("Empty image")
    if len(file_bytes) > MAX_AVATAR_BYTES:
        raise ValueError("Image too large (max 2MB)")
    ext = _ext_for_content_type(content_type)
    if not ext:
        raise ValueError("Unsupported image type")
    _clear_existing_files(user_id)
    path = avatars_dir() / f"{user_id}{ext}"
    path.write_bytes(file_bytes)
    return public_avatar_url(user_id)


def delete_avatar_files(user_id: UUID) -> None:
    _clear_existing_files(user_id)


def download_and_store_avatar(user_id: UUID, source_url: str) -> str | None:
    """Download a remote image and store it locally. Returns public URL or None."""
    if not source_url.startswith(("http://", "https://")):
        return None
    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(source_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type")
            ext = _ext_for_content_type(content_type)
            if not ext:
                # Some CDNs omit type; sniff from magic bytes
                data = response.content
                if data.startswith(b"\xff\xd8\xff"):
                    ext = ".jpg"
                    content_type = "image/jpeg"
                elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                    ext = ".png"
                    content_type = "image/png"
                elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                    ext = ".webp"
                    content_type = "image/webp"
                else:
                    logger.info("Skip avatar download: unsupported type %s", content_type)
                    return None
            else:
                data = response.content
            if len(data) > MAX_AVATAR_BYTES:
                logger.info("Skip avatar download: too large (%s bytes)", len(data))
                return None
            return store_upload(user_id, data, content_type)
    except Exception:
        logger.exception("Failed to download avatar from %s", source_url)
        return None
