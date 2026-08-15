from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.cookies import clear_auth_cookies, set_auth_cookie, set_refresh_cookie
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ErrorResponse,
    GoogleOneTapRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserRead,
)
from app.services.auth import (
    authenticate_user,
    change_password,
    delete_my_picture,
    get_or_create_google_user,
    issue_token_for_user,
    link_google_account,
    register_user,
    unlink_google_account,
    update_me,
    update_my_picture,
    user_to_read,
)
from app.services.avatars import MAX_AVATAR_BYTES
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
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return user_to_read(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update current user profile",
    description="Update Lunar display_name only. Never syncs name from Google.",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
def patch_me(
    payload: UpdateMeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = update_me(db, current_user, payload)
    return user_to_read(user)


@router.post(
    "/me/password",
    response_model=UserRead,
    summary="Change or set password",
    description=(
        "If the account already has a password, current_password is required. "
        "Google-only accounts can set a password without current_password."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Invalid current password"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        422: {"description": "Validation error"},
    },
)
def post_me_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = change_password(db, current_user, payload)
    return user_to_read(user)


@router.post(
    "/me/picture",
    response_model=UserRead,
    summary="Upload profile picture",
    description="Upload a local avatar image (jpeg/png/webp/gif, max 2MB).",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid image"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
async def post_me_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
) -> UserRead:
    data = await file.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image too large (max 2MB)",
        )
    user = update_my_picture(db, current_user, data, file.content_type)
    return user_to_read(user)


@router.delete(
    "/me/picture",
    response_model=UserRead,
    summary="Delete profile picture",
    responses={401: {"model": ErrorResponse, "description": "Not authenticated"}},
)
def delete_me_picture(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = delete_my_picture(db, current_user)
    return user_to_read(user)


@router.post(
    "/google/link",
    response_model=UserRead,
    summary="Link Google to current account",
    description=(
        "Verify a GIS credential and attach google_sub to the logged-in user. "
        "Does not change display_name. May copy avatar locally if missing."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Invalid Google credential"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        503: {"model": ErrorResponse, "description": "Google sign-in not configured"},
    },
)
def google_link(
    payload: GoogleOneTapRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
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

    user = link_google_account(
        db,
        current_user,
        google_sub=token_payload["sub"],
        email=token_payload["email"],
        picture=token_payload.get("picture"),
    )
    return user_to_read(user)


@router.post(
    "/google/unlink",
    response_model=UserRead,
    summary="Unlink Google from current account",
    description="Requires a password on the account so the user can still sign in.",
    responses={
        400: {"model": ErrorResponse, "description": "Cannot unlink"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def google_unlink(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    user = unlink_google_account(db, current_user)
    return user_to_read(user)


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
        "and set the session cookie. Does not copy Google display name."
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
        picture=token_payload.get("picture"),
    )
    return _token_response_with_cookie(user, db, status.HTTP_200_OK)
