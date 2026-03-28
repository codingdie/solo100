"""Approval Gateway — processes all human-intervention decisions.

Thread safety: All state transitions use SELECT FOR UPDATE on the Feature row.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feature import Feature, FeatureStatus
from app.models.feature_execution import ExecutionStage, ExecutionStatus, FeatureExecution
from app.services.notification_hub import (
    notify_awaiting_approval,
    notify_error,
    notify_status_changed,
)

logger = logging.getLogger(__name__)

ActionType = Literal["approve", "reject", "ignore_test_failure", "retry_verification"]


class InvalidActionError(Exception):
    pass


class ApprovalGateway:
    """Processes human decisions at the 4 approval gate nodes."""

    TRANSITIONS: dict[tuple[str, ActionType], str | None] = {
        (FeatureStatus.BRAINSTORMING.value, "approve"): FeatureStatus.PLANNING.value,
        (FeatureStatus.BRAINSTORMING.value, "reject"): FeatureStatus.BRAINSTORMING.value,
        (FeatureStatus.PLANNING.value, "approve"): FeatureStatus.IMPLEMENTING.value,
        (FeatureStatus.PLANNING.value, "reject"): FeatureStatus.BRAINSTORMING.value,
        (FeatureStatus.TESTING.value, "approve"): FeatureStatus.REVIEWING.value,
        (FeatureStatus.TESTING.value, "reject"): FeatureStatus.BRAINSTORMING.value,
        (FeatureStatus.TESTING.value, "ignore_test_failure"): FeatureStatus.REVIEWING.value,
        (FeatureStatus.REVIEWING.value, "approve"): FeatureStatus.APPROVED.value,
        (FeatureStatus.REVIEWING.value, "reject"): FeatureStatus.BRAINSTORMING.value,
        (FeatureStatus.APPROVED.value, "retry_verification"): FeatureStatus.VERIFYING.value,
    }

    async def handle(
        self, db: AsyncSession, feature_id: str,
        action: ActionType, decided_by: str = "human",
    ) -> Feature:
        result = await db.execute(
            select(Feature).where(Feature.id == feature_id).with_for_update()
        )
        feature = result.scalar_one_or_none()
        if feature is None:
            raise InvalidActionError(f"Feature {feature_id} not found")

        current_status = feature.status
        next_status = self.TRANSITIONS.get((current_status, action))

        if next_status is None:
            raise InvalidActionError(
                f"Action '{action}' is not valid in Feature status '{current_status}'"
            )

        old_status = current_status
        retry_count = feature.retry_count or 0

        # Handle retry logic
        if action in ("reject",) and next_status == FeatureStatus.BRAINSTORMING.value:
            retry_count = retry_count + 1
            if retry_count >= feature.max_retries:
                logger.warning(
                    "Feature %s exceeded max_retries (%d), moving to failed",
                    feature.id, feature.max_retries,
                )
                await db.execute(
                    update(Feature).where(Feature.id == feature.id)
                    .values(
                        status=FeatureStatus.FAILED.value,
                        retry_count=retry_count,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await db.flush()
                feature.status = FeatureStatus.FAILED.value
                feature.retry_count = retry_count
                await notify_error(
                    feature.id, "approval_gateway",
                    f"Retry limit exceeded ({retry_count}/{feature.max_retries})",
                )
                return feature
            else:
                await db.execute(
                    update(Feature).where(Feature.id == feature.id)
                    .values(
                        status=next_status,
                        retry_count=retry_count,
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await db.flush()
                feature.status = next_status
                feature.retry_count = retry_count
        else:
            # Apply state transition (no retry involved)
            await db.execute(
                update(Feature).where(Feature.id == feature_id)
                .values(status=next_status, updated_at=datetime.now(timezone.utc))
            )
            await db.flush()
            feature.status = next_status

        logger.info(
            "ApprovalGateway: Feature %s %s %s → %s (decided_by=%s)",
            feature_id, action, old_status, next_status, decided_by,
        )

        # Write FeatureExecution record
        await self._write_transition_execution(
            db, feature, action, old_status, next_status, decided_by, retry_count,
        )

        # Push notifications
        await notify_status_changed(feature_id, old_status, next_status)

        return feature

    async def _increment_retry_and_check(self, db: AsyncSession, feature: Feature) -> None:
        feature.retry_count = (feature.retry_count or 0) + 1

        if feature.retry_count >= feature.max_retries:
            logger.warning(
                "Feature %s exceeded max_retries (%d), moving to failed",
                feature.id, feature.max_retries,
            )
            feature.status = FeatureStatus.FAILED.value
            await db.execute(
                update(Feature).where(Feature.id == feature.id)
                .values(
                    status=FeatureStatus.FAILED.value,
                    retry_count=feature.retry_count,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await notify_error(
                feature.id, "approval_gateway",
                f"Retry limit exceeded ({feature.retry_count}/{feature.max_retries})",
            )
        else:
            await db.execute(
                update(Feature).where(Feature.id == feature.id)
                .values(retry_count=feature.retry_count)
            )

    async def _write_transition_execution(
        self, db: AsyncSession, feature: Feature,
        action: ActionType, old_status: str, next_status: str,
        decided_by: str, retry_count: int,
    ) -> None:
        stage_map = {
            FeatureStatus.BRAINSTORMING.value: ExecutionStage.BRAINSTORMING,
            FeatureStatus.PLANNING.value: ExecutionStage.PLANNING,
            FeatureStatus.TESTING.value: ExecutionStage.TESTING,
            FeatureStatus.REVIEWING.value: ExecutionStage.REVIEWING,
        }
        stage = stage_map.get(old_status, ExecutionStage.BRAINSTORMING)

        record = FeatureExecution(
            id=str(uuid.uuid4()),
            feature_id=feature.id,
            attempt_number=retry_count + 1,
            stage=stage.value,
            status=ExecutionStatus.COMPLETED.value,
            result_json=json.dumps({
                "action": action, "decided_by": decided_by,
                "old_status": old_status, "next_status": next_status,
                "transitioned_at": datetime.now(timezone.utc).isoformat(),
            }),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(record)
        await db.flush()


gateway = ApprovalGateway()
