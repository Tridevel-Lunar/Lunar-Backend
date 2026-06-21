from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ErrorResponse, LoginRequest, RegisterRequest, TokenResponse, UserRead
from app.services.auth import (
    authenticate_user,
    get_or_create_google_user,
    issue_token_for_user,
    register_user,
)

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
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = register_user(db, payload)
    return TokenResponse(access_token=issue_token_for_user(user))


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
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    return TokenResponse(access_token=issue_token_for_user(user))


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Return the authenticated user. Requires Bearer JWT (Authorize in Swagger).",
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
        "Handles Google redirect, upserts the user, then redirects to the frontend "
        "with `access_token` query param."
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

    user = get_or_create_google_user(
        db,
        google_sub=google_sub,
        email=email,
        display_name=userinfo.get("name"),
    )
    access_token = issue_token_for_user(user)
    callback_url = f"{settings.frontend_url.rstrip('/')}/auth/callback"
    return RedirectResponse(url=f"{callback_url}?access_token={access_token}")
