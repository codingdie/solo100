"""AgentConfig ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentConfig(Base):
    """Configuration for a specific AI Agent (Claude Code, Codex, etc.)."""

    __tablename__ = "agent_config"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="claude_code",
    )
    api_key_env: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_default: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
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

    def __repr__(self) -> str:
        return f"<AgentConfig(id={self.id}, name={self.name}, type={self.type})>"
