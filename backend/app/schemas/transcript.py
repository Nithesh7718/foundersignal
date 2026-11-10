import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TranscriptResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    audio_asset_id: uuid.UUID | None = None
    provider: str
    model: str | None = None
    language_code: str | None = None
    raw_transcript: str
    status: str
    confidence: float | None = None
    metadata_payload: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
