import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.audio import AudioAssetResponse
from app.schemas.commitment import CommitmentResponse
from app.schemas.transcript import TranscriptResponse


class ConversationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    conversation_type: str = Field("voice_note", max_length=50)
    recorded_at: datetime | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    conversation_type: str
    status: str
    recorded_at: datetime
    created_at: datetime
    audio_assets: list[AudioAssetResponse] = []
    commitments_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    title: str
    conversation_type: str
    status: str
    recorded_at: datetime
    created_at: datetime
    audio_assets: list[AudioAssetResponse] = []
    transcripts: list[TranscriptResponse] = []
    commitments: list[CommitmentResponse] = []

    model_config = ConfigDict(from_attributes=True)
