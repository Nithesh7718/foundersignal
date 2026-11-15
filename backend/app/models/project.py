import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.commitment import Commitment
    from app.models.workspace import Workspace


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    # Status lifecycle: 'active', 'completed', 'on_hold', 'archived'
    status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        index=True,
        nullable=False,
    )
    target_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="projects",
    )
    commitments: Mapped[list["Commitment"]] = relationship(
        "Commitment",
        back_populates="project",
    )

    __table_args__ = (Index("ix_projects_workspace_status", "workspace_id", "status"),)
