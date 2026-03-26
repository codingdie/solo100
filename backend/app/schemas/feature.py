"""Pydantic schemas for Feature and related resources."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class FeatureBase(BaseModel):
    """Shared fields for Feature create/update."""

    title: Annotated[str, Field(min_length=1, max_length=500)]
    description: Annotated[str, Field(min_length=1)]


class FeatureCreate(FeatureBase):
    """Request body for POST /projects/{project_id}/features."""
    pass


class FeatureUpdate(BaseModel):
    """Request body for PUT /features/{id}; all fields optional."""

    title: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    description: str | None = None


class FeatureResponse(BaseModel):
    """Response body for single Feature GET."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    title: str
    description: str
    status: str
    branch: str | None
    pr_url: str | None
    worktree_path: str | None
    retry_count: int
    max_retries: int
    created_at: datetime
    updated_at: datetime


class FeatureListResponse(BaseModel):
    """Response body for GET /projects/{project_id}/features."""

    items: list[FeatureResponse]
    total: int


class FeatureExecutionResponse(BaseModel):
    """Response body for FeatureExecution records."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    feature_id: str
    attempt_number: int
    stage: str
    status: str
    result_json: str | None
    started_at: datetime
    finished_at: datetime | None


class FeatureExecutionListResponse(BaseModel):
    """Response body for GET /features/{id}/executions."""

    items: list[FeatureExecutionResponse]


class FeatureReviewResponse(BaseModel):
    """Response body for GET /features/{id}/review."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    feature_id: str
    attempt_number: int
    ai_summary: str | None
    ai_issues_json: str | None
    human_decision: str | None
    decided_by: str | None
    decided_at: datetime | None
    created_at: datetime
