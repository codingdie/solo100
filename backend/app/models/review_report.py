"""ReviewReport ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewReport(Base):
    """AI code review report for a Feature attempt."""

    __tablename__ = "review_report"

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
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_issues_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    feature: Mapped["Feature"] = relationship(
        "Feature",
        back_populates="review_reports",
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewReport(id={self.id}, feature_id={self.feature_id}, "
            f"human_decision={self.human_decision})>"
        )
