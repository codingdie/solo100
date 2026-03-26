"""Feature ORM model and status enum."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeatureStatus(str, Enum):
    """All possible states of a Feature."""

    PENDING = "pending"
    BRAINSTORMING = "brainstorming"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    VERIFYING = "verifying"
    MERGED = "merged"
    FAILED = "failed"
    ARCHIVED = "archived"


class Feature(Base):
    """A single Feature (user story / task) under a Project."""

    __tablename__ = "feature"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=FeatureStatus.PENDING.value,
    )
    branch: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="3",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="features")
    executions: Mapped[list["FeatureExecution"]] = relationship(
        "FeatureExecution",
        back_populates="feature",
        cascade="all, delete-orphan",
        order_by="FeatureExecution.started_at",
    )
    review_reports: Mapped[list["ReviewReport"]] = relationship(
        "ReviewReport",
        back_populates="feature",
        cascade="all, delete-orphan",
        order_by="ReviewReport.created_at",
    )

    def __repr__(self) -> str:
        return f"<Feature(id={self.id}, title={self.title}, status={self.status})>"
