import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import TokenValidationError, validate_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user import UserRepository

security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    if not credentials:
        raise UnauthorizedError("MISSING_TOKEN", "Authentication credentials were not provided.")

    try:
        user_id = validate_token(credentials.credentials, "access")
    except TokenValidationError as exc:
        raise UnauthorizedError("INVALID_TOKEN", str(exc)) from exc

    user = UserRepository(db).get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise UnauthorizedError("INVALID_TOKEN", "User not found or inactive.")
    return user


def get_request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", "req_local")
