"""REST router for Feature CRUD and state-transition operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feature import Feature
from app.models.feature_execution import FeatureExecution
from app.models.project import Project
from app.models.review_report import ReviewReport
from app.schemas.feature import (
    FeatureCreate,
    FeatureExecutionListResponse,
    FeatureExecutionResponse,
    FeatureListResponse,
    FeatureResponse,
    FeatureReviewResponse,
    FeatureUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["features"])


@router.get("/projects/{project_id}/features", response_model=FeatureListResponse)
async def list_features_by_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureListResponse:
    """Return all Features for a given project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if proj_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Feature)
        .where(Feature.project_id == project_id)
        .order_by(Feature.created_at.desc()),
    )
    items = result.scalars().all()
    return FeatureListResponse(
        items=[FeatureResponse.model_validate(f) for f in items],
        total=len(items),
    )


@router.post(
    "/projects/{project_id}/features",
    response_model=FeatureResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_feature(
    project_id: str,
    payload: FeatureCreate,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Create a new Feature under a project."""
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    if proj_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Project not found")

    feature = Feature(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
    )
    db.add(feature)
    await db.flush()
    await db.refresh(feature)
    return FeatureResponse.model_validate(feature)


@router.get("/features/{feature_id}", response_model=FeatureResponse)
async def get_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Return a single Feature by id."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return FeatureResponse.model_validate(feature)


@router.post("/features/{feature_id}/start", response_model=FeatureResponse)
async def start_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Transition a Feature from pending to brainstorming."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature start logic not yet implemented",
    )


@router.post("/features/{feature_id}/archive", response_model=FeatureResponse)
async def archive_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Move a Feature to archived status (terminal)."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature archive logic not yet implemented",
    )


@router.post("/features/{feature_id}/reset", response_model=FeatureResponse)
async def reset_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Reset retry_count to 0 and move a failed Feature back to brainstorming."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature reset logic not yet implemented",
    )


@router.get(
    "/features/{feature_id}/executions",
    response_model=FeatureExecutionListResponse,
)
async def list_feature_executions(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureExecutionListResponse:
    """Return all FeatureExecution records for a Feature."""
    result = await db.execute(
        select(FeatureExecution)
        .where(FeatureExecution.feature_id == feature_id)
        .order_by(FeatureExecution.started_at),
    )
    items = result.scalars().all()
    return FeatureExecutionListResponse(
        items=[FeatureExecutionResponse.model_validate(e) for e in items],
    )


@router.get(
    "/features/{feature_id}/review",
    response_model=FeatureReviewResponse | None,
)
async def get_feature_review(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureReviewResponse | None:
    """Return the most recent ReviewReport for a Feature, or None."""
    result = await db.execute(
        select(ReviewReport)
        .where(ReviewReport.feature_id == feature_id)
        .order_by(ReviewReport.attempt_number.desc()),
    )
    report = result.scalars().first()
    if report is None:
        return None
    return FeatureReviewResponse.model_validate(report)
