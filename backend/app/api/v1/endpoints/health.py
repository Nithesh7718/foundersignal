from fastapi import APIRouter, status

from app.core.config import settings
from app.core.database import check_db_connection
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Health Check",
    description="Returns service status, environment, version, and database connection state.",
)
def get_health() -> HealthResponse:
    db_ok = check_db_connection()
    overall_status = "healthy" if db_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        service="foundersignal-api",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
    )
