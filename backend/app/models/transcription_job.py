import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.audio_asset import AudioAsset
    from app.models.conversation import Conversation
    from app.models.transcript import Transcript
    from app.models.workspace import Workspace


class TranscriptionJob(Base, TimestampMixin):
    """Durable tracking of asynchronous and synchronous transcription jobs."""

    __tablename__ = "transcription_jobs"

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
    audio_asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("audio_assets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    transcript_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transcripts.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        default="gnani_prisma",
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        default="prisma-v3.0",
        nullable=False,
    )
    job_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,  # 'rest' or 'batch'
    )
    external_job_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="queued",
        index=True,
        nullable=False,
    )
    language_code: Mapped[str] = mapped_column(
        String(20),
        default="indic-auto",
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    progress_percent: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_poll_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
    )
    locked_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=True,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    lease_token: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="transcription_jobs",
        foreign_keys="[TranscriptionJob.conversation_id]",
    )
    audio_asset: Mapped["AudioAsset"] = relationship(
        "AudioAsset",
        foreign_keys="[TranscriptionJob.audio_asset_id]",
    )
    transcript: Mapped["Transcript | None"] = relationship("Transcript")

    __table_args__ = (
        # Composite foreign key enforcing conversation belongs to the exact same workspace
        ForeignKeyConstraint(
            ["conversation_id", "workspace_id"],
            ["conversations.id", "conversations.workspace_id"],
            ondelete="CASCADE",
            name="fk_transcription_jobs_conversation_workspace",
        ),
        # Composite foreign key enforcing audio asset belongs to exact same workspace
        # and conversation
        ForeignKeyConstraint(
            ["audio_asset_id", "workspace_id", "conversation_id"],
            ["audio_assets.id", "audio_assets.workspace_id", "audio_assets.conversation_id"],
            ondelete="CASCADE",
            name="fk_transcription_jobs_audio_workspace_conversation",
        ),
        # Partial unique index: only ONE active job allowed per audio asset at any time
        # Protected against concurrent duplicate submissions, ambiguous submission retries,
        # and unconfirmed cancellations.
        Index(
            "uq_active_transcription_job_per_asset",
            "audio_asset_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'submitting', 'submitted', "
                "'submission_unknown', 'cancelled_unconfirmed', 'processing')"
            ),
        ),
        # Scoped unique index on (provider, external_job_id) to prevent collision within a provider
        Index(
            "uq_transcription_jobs_provider_external_id",
            "provider",
            "external_job_id",
            unique=True,
            postgresql_where=text("external_job_id IS NOT NULL"),
        ),
        # Compound index for multi-tenant conversation job queries
        Index(
            "ix_transcription_jobs_workspace_conversation",
            "workspace_id",
            "conversation_id",
        ),
        # Compound index for worker polling queue
        Index(
            "ix_transcription_jobs_status_next_poll",
            "status",
            "next_poll_at",
        ),
        # Compound index for worker lease recovery
        Index(
            "ix_transcription_jobs_status_lease",
            "status",
            "lease_expires_at",
        ),
    )
