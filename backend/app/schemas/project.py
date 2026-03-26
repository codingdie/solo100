"""Pydantic schemas for Project."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Shared fields for Project create/update."""

    name: Annotated[str, Field(min_length=1, max_length=255)]
    ssh_url: Annotated[str, Field(min_length=1, max_length=1024)]
    default_branch: Annotated[str, Field(min_length=1, max_length=255)] = "main"
    ssh_key_env: Annotated[str, Field(min_length=1, max_length=255)]
    default_agent_id: str | None = None


class ProjectCreate(ProjectBase):
    """Request body for POST /projects."""
    pass


class ProjectUpdate(BaseModel):
    """Request body for PUT /projects/{id}; all fields optional."""

    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    ssh_url: Annotated[str, Field(min_length=1, max_length=1024)] | None = None
    default_branch: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    ssh_key_env: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    default_agent_id: str | None = None


class ProjectResponse(BaseModel):
    """Response body for single Project GET."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    ssh_url: str
    default_branch: str
    ssh_key_env: str
    default_agent_id: str | None
    created_at: datetime


class ProjectListResponse(BaseModel):
    """Response body for GET /projects (list)."""

    items: list[ProjectResponse]
    total: int
