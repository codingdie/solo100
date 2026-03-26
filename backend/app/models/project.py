"""Project ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    """A Git repository project that hosts Features."""

    __tablename__ = "project"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ssh_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="main",
    )
    ssh_key_env: Mapped[str] = mapped_column(String(255), nullable=False)
    default_agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_config.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    features: Mapped[list["Feature"]] = relationship(
        "Feature",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    default_agent: Mapped["AgentConfig | None"] = relationship(
        "AgentConfig",
        foreign_keys=[default_agent_id],
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
