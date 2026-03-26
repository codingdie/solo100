"""FeatureExecution ORM model and stage enum."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExecutionStage(str, Enum):
    """Stages that produce a FeatureExecution record."""

    BRAINSTORMING = "brainstorming"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    VERIFYING = "verifying"


class ExecutionStatus(str, Enum):
    """Status of a FeatureExecution record."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FeatureExecution(Base):
    """Record of a single stage execution within a Feature attempt."""

    __tablename__ = "feature_execution"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    feature_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("feature.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    feature: Mapped["Feature"] = relationship(
        "Feature",
        back_populates="executions",
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureExecution(id={self.id}, feature_id={self.feature_id}, "
            f"stage={self.stage}, status={self.status})>"
        )
