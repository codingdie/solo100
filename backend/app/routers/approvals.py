"""REST router for human-intervention approval/rejection operations."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feature import Feature
from app.schemas.feature import FeatureResponse

router = APIRouter(prefix="/api/v1/features", tags=["approvals"])


async def _get_feature_or_404(
    feature_id: str,
    db: AsyncSession,
) -> Feature:
    """Helper: fetch a Feature by id or raise 404."""
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.post("/{feature_id}/approve", response_model=FeatureResponse)
async def approve_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Generic approve: advance the Feature from any waiting state."""
    feature = await _get_feature_or_404(feature_id, db)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature approval logic not yet implemented",
    )


@router.post("/{feature_id}/reject", response_model=FeatureResponse)
async def reject_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Generic reject: move the Feature back to brainstorming."""
    feature = await _get_feature_or_404(feature_id, db)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature rejection logic not yet implemented",
    )


@router.post("/{feature_id}/ignore-test-failure", response_model=FeatureResponse)
async def ignore_test_failure(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Ignore the test failure in the testing stage, proceed to reviewing."""
    feature = await _get_feature_or_404(feature_id, db)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Ignore test failure logic not yet implemented",
    )


@router.post("/{feature_id}/retry-verification", response_model=FeatureResponse)
async def retry_verification(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Re-trigger the verifying stage from the approved state."""
    feature = await _get_feature_or_404(feature_id, db)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Retry verification logic not yet implemented",
    )
