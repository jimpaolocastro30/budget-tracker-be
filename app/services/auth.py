import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_token,
    verify_password,
)
from app.db.models.user import User
from app.repositories.category import CategoryRepository
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse, UserRegister, UserResponse

settings = get_settings()


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.categories = CategoryRepository(db)

    def register(self, data: UserRegister) -> TokenResponse:
        if self.users.get_by_email(data.email):
            raise ConflictError("EMAIL_EXISTS", "A user with this email already exists.")

        user = User(
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            base_currency=data.base_currency.upper(),
            timezone=data.timezone,
        )
        user = self.users.create(user)
        self.categories.seed_defaults()
        return self._build_token_response(user)

    def login(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email.lower())
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("INVALID_CREDENTIALS", "Invalid email or password.")
        if not user.is_active:
            raise UnauthorizedError("ACCOUNT_INACTIVE", "Account is deactivated.")
        return self._build_token_response(user)

    def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            user_id = validate_token(refresh_token, "refresh")
        except TokenValidationError as exc:
            raise UnauthorizedError("INVALID_TOKEN", str(exc)) from exc

        stored = self.users.get_refresh_token(refresh_token)
        if not stored or stored.expires_at < datetime.now(UTC):
            raise UnauthorizedError("INVALID_TOKEN", "Refresh token is invalid or expired.")

        user = self.users.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedError("INVALID_TOKEN", "User not found or inactive.")

        self.users.revoke_refresh_token(refresh_token)
        return self._build_token_response(user)

    def logout(self, refresh_token: str) -> None:
        self.users.revoke_refresh_token(refresh_token)

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("INVALID_PASSWORD", "Current password is incorrect.")
        user.password_hash = hash_password(new_password)
        self.users.update(user)
        self.users.revoke_all_user_tokens(user.id)

    def _build_token_response(self, user: User) -> TokenResponse:
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        self.users.store_refresh_token(user.id, refresh_token, expires_at)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse.model_validate(user),
        )
