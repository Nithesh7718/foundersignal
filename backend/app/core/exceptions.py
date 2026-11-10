from typing import Any

from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        message: str = "An unexpected error occurred.",
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                }
            },
            headers=headers,
        )
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundException(AppException):
    def __init__(self, resource: str, identifier: Any = None):
        if identifier is not None:
            message = f"{resource} with identifier '{identifier}' was not found."
            details = {"resource": resource, "identifier": str(identifier)}
        else:
            message = resource
            details = {}
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            message=message,
            details=details,
        )


class ValidationException(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        super().__init__(
            status_code=status_code,
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str = "Could not validate authentication credentials."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_REQUIRED",
            message=message,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "You do not have permission to access this resource."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCESS_DENIED",
            message=message,
        )


class ConflictException(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            code="RESOURCE_CONFLICT",
            message=message,
            details=details,
        )


class PayloadTooLargeException(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        status_code = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
        super().__init__(
            status_code=status_code,
            code="PAYLOAD_TOO_LARGE",
            message=message,
            details=details,
        )


class ExternalProviderException(AppException):
    def __init__(self, provider: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="EXTERNAL_PROVIDER_ERROR",
            message=f"Error communicating with provider {provider}: {message}",
            details={"provider": provider, **(details or {})},
        )
