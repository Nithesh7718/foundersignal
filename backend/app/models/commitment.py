import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
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
    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
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
    )
