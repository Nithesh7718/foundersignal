from typing import Any

from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        message: str = "An unexpected error occurred.",
        details: dict[str, Any] | None = None,
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
        )
        self.code = code
        self.message = message
        self.details = details or {}


class NotFoundException(AppException):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} with identifier '{identifier}' was not found.",
            details={"resource": resource, "identifier": str(identifier)},
        )


class ValidationException(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
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
