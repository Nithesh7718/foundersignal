import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.user import User


class Commitment(Base, TimestampMixin):
    __tablename__ = "commitments"

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
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Status lifecycle: 'inferred' (awaiting user confirmation),
    # 'confirmed', 'rejected', 'in_progress', 'completed'
    status: Mapped[str] = mapped_column(
        String(50),
        default="inferred",
        index=True,
        nullable=False,
    )
    # Extraction confidence score (nullable when unavailable or uncertified)
    confidence_score: Mapped[float | None] = mapped_column(
        Float,
        default=None,
        nullable=True,
    )
    # Evidence fields
    source_quote: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    speaker: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    timestamp_start: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    timestamp_end: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    # SHA-256 fingerprint for deduplication and concurrent extraction idempotency
    evidence_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )
    # Review audit fields
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # Operational fields
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="commitments",
    )
    assignee: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[assignee_id],
    )
    reviewed_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[reviewed_by_id],
    )

    __table_args__ = (
        Index(
            "uq_commitments_conv_evidence_hash",
            "conversation_id",
            "evidence_hash",
            unique=True,
            postgresql_where=text("evidence_hash IS NOT NULL"),
        ),
    )
