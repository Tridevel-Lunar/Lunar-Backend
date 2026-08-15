from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.avatars import avatar_file_path

router = APIRouter(tags=["avatars"])


@router.get(
    "/avatars/{user_id}",
    summary="Get user avatar image",
    responses={404: {"description": "Avatar not found"}},
)
def get_avatar(user_id: UUID) -> FileResponse:
    path = avatar_file_path(user_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found")
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=3600"})
