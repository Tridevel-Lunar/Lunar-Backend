from starlette.responses import Response

from app.core.config import get_settings


def set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=max_age,
        secure=settings.auth_cookie_secure,
    )


def clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/")
