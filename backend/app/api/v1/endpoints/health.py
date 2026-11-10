from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import check_db_connection
from app.schemas.health import LivenessResponse, ReadinessResponse

router = APIRouter()


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Liveness Check",
    description=(
        "Returns HTTP 200 if the application process is running and accepting HTTP requests."
    ),
)
def get_liveness() -> LivenessResponse:
    return LivenessResponse(
        status="alive",
        service="foundersignal-api",
        version=settings.VERSION,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={
        200: {"description": "Service and all dependencies are healthy and ready."},
        503: {"description": "Service dependencies (e.g. PostgreSQL) are unavailable."},
    },
    summary="Service Readiness Check",
    description="Returns HTTP 200 if PostgreSQL is accessible, HTTP 503 if unavailable.",
)
def get_readiness() -> Response:
    db_ok = check_db_connection()

    if db_ok:
        payload = ReadinessResponse(
            status="ready",
            service="foundersignal-api",
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            database_connected=True,
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=payload.model_dump(mode="json"),
        )

    payload = ReadinessResponse(
        status="unavailable",
        service="foundersignal-api",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_connected=False,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(mode="json"),
    )


@router.get(
    "/health",
    response_model=ReadinessResponse,
    summary="General Service Health Check",
    description="Alias for readiness check returning service and database status.",
)
def get_health() -> Response:
    return get_readiness()
