import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TranscriptionJobCreate(BaseModel):
    audio_asset_id: uuid.UUID
    language_code: str = Field("indic-auto", max_length=20)


class TranscriptionJobResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    audio_asset_id: uuid.UUID
    transcript_id: uuid.UUID | None = None
    provider: str
    model: str
    job_type: str
    external_job_id: str | None = None
    status: str
    language_code: str
    attempt_count: int
    progress_percent: int
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_poll_at: datetime | None = None
    last_polled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
