from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.cookies import clear_auth_cookies, set_auth_cookie, set_refresh_cookie
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ErrorResponse,
    GoogleOneTapRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.services.auth import (
    authenticate_user,
    get_or_create_google_user,
    issue_token_for_user,
    register_user,
)
from app.services.google_auth import GoogleAuthError, verify_google_id_token
from app.services.refresh_token import create_refresh_token, revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["auth"])
oauth = OAuth()
_settings = get_settings()

if _settings.google_oauth_enabled:
    oauth.register(
        name="google",
        client_id=_settings.google_client_id,
        client_secret=_settings.google_client_secret,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def _token_response_with_cookie(user: User, db: Session, status_code: int) -> JSONResponse:
    access_token = issue_token_for_user(user)
    refresh_token = create_refresh_token(db, user.id)
    response = JSONResponse(
        content=TokenResponse(access_token=access_token).model_dump(),
        status_code=status_code,
    )
    set_auth_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token)
    return response


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register with email and password",
    description="Create a new user account and return a JWT access token.",
    responses={
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"description": "Validation error"},
    },
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> JSONResponse:
    user = register_user(db, payload)
    return _token_response_with_cookie(user, db, status.HTTP_201_CREATED)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    description="Authenticate with email/password and return a JWT access token.",
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        422: {"description": "Validation error"},
    },
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> JSONResponse:
    user = authenticate_user(db, payload.email, payload.password)
    return _token_response_with_cookie(user, db, status.HTTP_200_OK)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description=(
        "Exchange a valid refresh token cookie for a new access token. "
        "Rotates the refresh token on success."
    ),
    responses={401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"}},
)
def refresh_session(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    user, new_refresh_token = rotate_refresh_token(db, refresh_token)
    access_token = issue_token_for_user(user)
    response = JSONResponse(content=TokenResponse(access_token=access_token).model_dump())
    set_auth_cookie(response, access_token)
    set_refresh_cookie(response, new_refresh_token)
    return response


@router.post(
    "/logout",
    summary="Logout",
    description="Revoke refresh token and clear session cookies.",
)
def logout(request: Request, db: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        revoke_refresh_token(db, refresh_token)

    response = JSONResponse(content={"ok": True})
    clear_auth_cookies(response)
    return response


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Return the authenticated user. Requires Bearer JWT or session cookie.",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get(
    "/google",
    summary="Start Google OAuth login",
    description=(
        "Browser redirect flow to Google consent screen. "
        "Not fully testable from Swagger — open this URL in a browser."
    ),
    responses={
        503: {"model": ErrorResponse, "description": "Google OAuth not configured"},
    },
)
async def google_login(request: Request):
    settings = get_settings()
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/google/callback",
    summary="Google OAuth callback",
    description=(
        "Handles Google redirect, upserts the user, sets session cookie, "
        "then redirects to the frontend Space module."
    ),
    responses={
        503: {"model": ErrorResponse, "description": "Google OAuth not configured"},
    },
)
async def google_callback(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.google_oauth_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )

    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return user info",
        )

    google_sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not google_sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account missing required fields",
        )
    if not userinfo.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google email is not verified",
        )

    user = get_or_create_google_user(
        db,
        google_sub=google_sub,
        email=email,
        display_name=userinfo.get("name"),
        picture=userinfo.get("picture"),
    )
    access_token = issue_token_for_user(user)
    refresh_token = create_refresh_token(db, user.id)
    space_url = f"{settings.frontend_url.rstrip('/')}/space"
    response = RedirectResponse(url=space_url)
    set_auth_cookie(response, access_token)
    set_refresh_cookie(response, refresh_token)
    return response


@router.post(
    "/google/onetap",
    response_model=TokenResponse,
    summary="Sign in with Google One Tap",
    description=(
        "Verify a Google Identity Services credential JWT, upsert the user, "
        "and set the session cookie."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid Google credential"},
        503: {"model": ErrorResponse, "description": "Google sign-in not configured"},
    },
)
def google_onetap(payload: GoogleOneTapRequest, db: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()
    if not settings.google_onetap_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured",
        )

    try:
        token_payload = verify_google_id_token(payload.credential)
    except GoogleAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    user = get_or_create_google_user(
        db,
        google_sub=token_payload["sub"],
        email=token_payload["email"],
        display_name=token_payload.get("name"),
        picture=token_payload.get("picture"),
    )
    return _token_response_with_cookie(user, db, status.HTTP_200_OK)
