from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.common import ORMModel


class UserRegister(ORMModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    base_currency: str = Field(default="PHP", min_length=3, max_length=3)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)


class UserLogin(ORMModel):
    email: EmailStr
    password: str


class UserUpdate(ORMModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)


class ChangePassword(ORMModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class UserResponse(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    base_currency: str
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class RefreshTokenRequest(ORMModel):
    refresh_token: str
