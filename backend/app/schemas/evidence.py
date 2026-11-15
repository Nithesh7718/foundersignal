import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # conversation, audio, transcript, commitment, project, speaker, assignee
    metadata: dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceGraphResponse(BaseModel):
    workspace_id: uuid.UUID
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    total_conversations: int
    total_audio_assets: int
    total_transcripts: int
    total_commitments: int
    total_projects: int

    model_config = ConfigDict(from_attributes=True)
