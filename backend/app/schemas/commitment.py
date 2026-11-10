import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommitmentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    source_quote: str
    speaker: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
