from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import get_settings


class GoogleAuthError(Exception):
    pass


def verify_google_id_token(credential: str) -> dict:
    """Validate a Google One Tap / GIS credential JWT."""
    settings = get_settings()
    if not settings.google_client_id:
        raise GoogleAuthError("Google sign-in is not configured")

    try:
        payload = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise GoogleAuthError("Invalid Google credential") from exc

    if not payload.get("email_verified", False):
        raise GoogleAuthError("Google email is not verified")

    email = payload.get("email")
    if not email:
        raise GoogleAuthError("Google credential missing email")

    google_sub = payload.get("sub")
    if not google_sub:
        raise GoogleAuthError("Google credential missing subject")

    return payload
