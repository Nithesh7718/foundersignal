import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

VALID_COMMITMENT_STATUSES = {
    "inferred",
    "confirmed",
    "rejected",
    "in_progress",
    "completed",
}

VALID_COMMITMENT_TRANSITIONS: dict[str, set[str]] = {
    "inferred": {"confirmed", "rejected"},
    "confirmed": {"in_progress", "completed", "rejected"},
    "rejected": {"inferred"},  # rejected commitments can only be reopened to inferred
    "in_progress": {"completed"},
    "completed": set(),  # terminal state: no further transitions allowed
}


class CommitmentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    source_quote: str = Field(..., min_length=1)
    status: str = Field("inferred", max_length=50)
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    speaker: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    evidence_hash: str | None = None


class CommitmentUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(None, max_length=50)
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None


class CommitmentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    title: str
    description: str | None = None
    status: str
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)
    source_quote: str
    speaker: str | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    evidence_hash: str | None = None
    reviewed_by_id: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    assignee_id: uuid.UUID | None = None
    due_date: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
