import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now

if TYPE_CHECKING:
    from app.models.audio_asset import AudioAsset
    from app.models.commitment import Commitment
    from app.models.transcript import Transcript
    from app.models.workspace import Workspace


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    conversation_type: Mapped[str] = mapped_column(
        String(50),
        default="voice_note",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        index=True,
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="conversations",
    )
    audio_assets: Mapped[list["AudioAsset"]] = relationship(
        "AudioAsset",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    commitments: Mapped[list["Commitment"]] = relationship(
        "Commitment",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
