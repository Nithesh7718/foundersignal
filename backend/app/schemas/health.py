from datetime import UTC, datetime

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall service status ('healthy' or 'degraded')")
    service: str = Field("foundersignal-api", description="Service identifier")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Current running environment")
    database_connected: bool = Field(..., description="Database connectivity status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server UTC timestamp",
    )
