"""Pydantic schemas for AgentConfig."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class AgentConfigBase(BaseModel):
    """Shared fields for AgentConfig create/update."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    type: Annotated[str, Field(min_length=1, max_length=32)] = "claude_code"
    api_key_env: Annotated[str, Field(min_length=1, max_length=255)]
    is_default: bool = False


class AgentConfigCreate(AgentConfigBase):
    """Request body for POST /agents."""
    pass


class AgentConfigUpdate(BaseModel):
    """Request body for PUT /agents/{id}; all fields optional."""

    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    type: Annotated[str, Field(min_length=1, max_length=32)] | None = None
    api_key_env: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    is_default: bool | None = None


class AgentConfigResponse(BaseModel):
    """Response body for AgentConfig."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    api_key_env: str
    is_default: bool
    created_at: datetime
    updated_at: datetime


class AgentConfigListResponse(BaseModel):
    """Response body for GET /agents."""

    items: list[AgentConfigResponse]
    total: int
