from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UpdateMeRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    display_name: str | None
    picture: str | None = None
    role: str
    created_at: datetime
    google_linked: bool = False
    has_password: bool = False

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str


class GoogleOneTapRequest(BaseModel):
    credential: str = Field(min_length=1)
