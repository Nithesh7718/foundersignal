import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    status: str = Field("active", max_length=50)
    target_date: datetime | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    status: str | None = Field(None, max_length=50)
    target_date: datetime | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    description: str | None = None
    status: str
    target_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    total_commitments: int = 0
    completed_commitments: int = 0
    in_progress_commitments: int = 0
    confirmed_commitments: int = 0
    inferred_commitments: int = 0
    overdue_commitments: int = 0

    model_config = ConfigDict(from_attributes=True)


class ProjectDeliverySummary(BaseModel):
    total_projects: int
    active_projects: int
    completed_projects: int
    total_commitments: int
    completed_commitments: int
    in_progress_commitments: int
    overdue_commitments: int
    delivery_completion_rate: float
