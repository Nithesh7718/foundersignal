import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AudioAssetResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    conversation_id: uuid.UUID
    file_name: str
    file_size_bytes: int
    mime_type: str
    duration_seconds: float | None = None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
