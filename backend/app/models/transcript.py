import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "workspace_id",
            "conversation_id",
            name="uq_transcripts_id_workspace_conversation",
        ),
        ForeignKeyConstraint(
            ["conversation_id", "workspace_id"],
            ["conversations.id", "conversations.workspace_id"],
            ondelete="CASCADE",
            name="fk_transcripts_conversation_workspace",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    audio_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    language_code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    raw_transcript: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    metadata_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="transcripts",
        foreign_keys="[Transcript.conversation_id]",
    )
