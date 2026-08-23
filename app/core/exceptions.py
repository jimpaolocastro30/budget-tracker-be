from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(code, message, status_code=404, details=details)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(code, message, status_code=409, details=details)


class UnauthorizedError(AppError):
    def __init__(self, code: str = "UNAUTHORIZED", message: str = "Not authenticated") -> None:
        super().__init__(code, message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, code: str = "FORBIDDEN", message: str = "Insufficient permission") -> None:
        super().__init__(code, message, status_code=403)
