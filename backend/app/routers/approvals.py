"""REST router for human-intervention approval/rejection operations."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.feature import FeatureResponse
from app.services.approval_gateway import ApprovalGateway, InvalidActionError

router = APIRouter(prefix="/api/v1/features", tags=["approvals"])

_gateway = ApprovalGateway()


async def _handle_action(
    feature_id: str, action: str, db: AsyncSession,
) -> FeatureResponse:
    try:
        feature = await _gateway.handle(db, feature_id, action)  # type: ignore[arg-type]
        return FeatureResponse.model_validate(feature)
    except InvalidActionError as exc:
        if "not found" in str(exc):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{feature_id}/approve", response_model=FeatureResponse)
async def approve_feature(
    feature_id: str, db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    return await _handle_action(feature_id, "approve", db)


@router.post("/{feature_id}/reject", response_model=FeatureResponse)
async def reject_feature(
    feature_id: str, db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    return await _handle_action(feature_id, "reject", db)


@router.post("/{feature_id}/ignore-test-failure", response_model=FeatureResponse)
async def ignore_test_failure(
    feature_id: str, db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    return await _handle_action(feature_id, "ignore_test_failure", db)


@router.post("/{feature_id}/retry-verification", response_model=FeatureResponse)
async def retry_verification(
    feature_id: str, db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    return await _handle_action(feature_id, "retry_verification", db)
