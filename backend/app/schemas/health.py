from datetime import UTC, datetime

from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = Field("alive", description="Process liveness indicator")
    service: str = Field("foundersignal-api", description="Service identifier")
    version: str = Field(..., description="Service version")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server UTC timestamp",
    )


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="Overall readiness status ('ready' or 'unavailable')")
    service: str = Field("foundersignal-api", description="Service identifier")
    version: str = Field(..., description="Service version")
    environment: str = Field(..., description="Current running environment")
    database_connected: bool = Field(..., description="Database connectivity status")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Current server UTC timestamp",
    )


class HealthResponse(ReadinessResponse):
    """Backwards-compatible health response schema."""

    pass
