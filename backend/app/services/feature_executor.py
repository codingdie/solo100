"""Feature Executor — core state machine driver.

Manages the lifecycle of a single Feature through all pipeline stages:
  pending → brainstorming → planning → implementing → testing
  → reviewing → approved → verifying → merged
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import asdict

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_context
from app.models.feature import Feature, FeatureStatus
from app.models.feature_execution import ExecutionStage, ExecutionStatus, FeatureExecution
from app.models.project import Project
from app.services.git_manager import IGitManager, git_manager as _git_manager
from app.services.notification_hub import (
    notify_awaiting_approval,
    notify_error,
    notify_stage_completed,
    notify_status_changed,
)
from app.services.review_engine import ReviewEngineStub
from app.services.stage_results import (
    BrainstormResult,
    ImplementResult,
    Plan,
    TestResult,
    VerificationResult,
)

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5
MAX_WAIT_CYCLES = 360


class FeatureExecutorError(Exception):
    pass


class RetryLimitExceeded(FeatureExecutorError):
    pass


class ApprovalTimeout(FeatureExecutorError):
    pass


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[-\s]+", "-", slug).strip("-")
    return slug[:64]


class FeatureExecutor:
    """State machine driver for a single Feature."""

    def __init__(
        self,
        git_manager: IGitManager | None = None,
        poll_interval: int = POLL_INTERVAL,
        max_wait_cycles: int = MAX_WAIT_CYCLES,
    ) -> None:
        self._git: IGitManager = git_manager or _git_manager
        self._review_engine = ReviewEngineStub()
        self._poll_interval = poll_interval
        self._max_wait_cycles = max_wait_cycles

    # ── Public API ────────────────────────────────────────────────────────

    async def run_pipeline(self, feature_id: str) -> dict:
        try:
            async with get_db_context() as db:
                feature = await self._load_feature(db, feature_id)

                if feature.status not in (
                    FeatureStatus.PENDING.value,
                    FeatureStatus.BRAINSTORMING.value,
                ):
                    return {
                        "success": False,
                        "final_status": feature.status,
                        "error": f"Feature is in status {feature.status}, cannot start pipeline",
                    }

                # Stage 1: Brainstorming
                await self._transition_to(db, feature, FeatureStatus.BRAINSTORMING.value)
                await self._run_brainstorming(db, feature)
                await self._wait_for_approval(db, feature, ExecutionStage.BRAINSTORMING.value)

                feature = await self._load_feature(db, feature_id)
                if feature.status != FeatureStatus.PLANNING.value:
                    return {"success": False, "final_status": feature.status,
                            "error": "Brainstorming approval did not advance to planning"}

                # Stage 2: Planning
                await self._run_planning(db, feature)
                await self._wait_for_approval(db, feature, ExecutionStage.PLANNING.value)

                feature = await self._load_feature(db, feature_id)
                if feature.status != FeatureStatus.IMPLEMENTING.value:
                    return {"success": False, "final_status": feature.status,
                            "error": "Plan approval did not advance to implementing"}

                # Stage 3: Implementing
                await self._run_implementing(db, feature)

                # Stage 4: Testing
                await self._transition_to(db, feature, FeatureStatus.TESTING.value)
                await self._run_testing(db, feature)
                await self._wait_for_approval(db, feature, ExecutionStage.TESTING.value)

                feature = await self._load_feature(db, feature_id)
                if feature.status not in (FeatureStatus.REVIEWING.value, FeatureStatus.BRAINSTORMING.value):
                    return {"success": False, "final_status": feature.status,
                            "error": f"Post-testing status {feature.status} is unexpected"}

                if feature.status == FeatureStatus.REVIEWING.value:
                    # Stage 5: Reviewing
                    await self._run_reviewing(db, feature)
                    await self._wait_for_approval(db, feature, ExecutionStage.REVIEWING.value)

                    feature = await self._load_feature(db, feature_id)
                    if feature.status != FeatureStatus.APPROVED.value:
                        return {"success": False, "final_status": feature.status,
                                "error": "Review approval did not advance to approved"}

                    # Stage 6: Verifying
                    await self._transition_to(db, feature, FeatureStatus.VERIFYING.value)
                    verify_result = await self._run_verifying(db, feature)

                    if verify_result.passed:
                        await self._transition_to(db, feature, FeatureStatus.MERGED.value)
                    else:
                        await self._transition_to(db, feature, FeatureStatus.APPROVED.value)
                        await notify_error(
                            feature.id, ExecutionStage.VERIFYING.value,
                            f"Verification failed: {verify_result.error_message}",
                        )
                        return {"success": False, "final_status": FeatureStatus.APPROVED.value,
                                "error": verify_result.error_message}

                return {"success": True, "final_status": feature.status, "error": None}

        except RetryLimitExceeded as exc:
            async with get_db_context() as db:
                await self._set_failed(db, feature_id, str(exc))
            return {"success": False, "final_status": FeatureStatus.FAILED.value, "error": str(exc)}

        except ApprovalTimeout as exc:
            return {"success": False, "final_status": FeatureStatus.BRAINSTORMING.value,
                    "error": f"Approval timeout: {exc}"}

        except Exception as exc:
            logger.exception("Unexpected error in FeatureExecutor for %s", feature_id)
            async with get_db_context() as db:
                await self._set_failed(db, feature_id, str(exc))
            return {"success": False, "final_status": FeatureStatus.FAILED.value, "error": str(exc)}

    # ── Stage execution helpers ───────────────────────────────────────────

    async def _run_brainstorming(self, db: AsyncSession, feature: Feature) -> None:
        logger.info("Stage brainstorming started for Feature %s", feature.id)

        result = BrainstormResult(
            analysis=f"[STUB] AI analysis of: {feature.title}\n\n{feature.description}",
            acceptance_criteria=[
                f"Feature '{feature.title}' is fully implemented",
                "All unit tests pass",
                "Code is reviewed and approved",
            ],
            key_points=["Implement the core feature logic", "Add corresponding unit tests"],
            estimated_risk="medium",
        )

        await self._write_execution(
            db, feature, ExecutionStage.BRAINSTORMING, ExecutionStatus.COMPLETED, result.to_dict(),
        )
        await notify_stage_completed(feature.id, ExecutionStage.BRAINSTORMING.value, result.to_dict())

    async def _run_planning(self, db: AsyncSession, feature: Feature) -> None:
        logger.info("Stage planning started for Feature %s", feature.id)

        result = Plan(
            tasks=[
                {"title": f"Implement {feature.title}", "file_patterns": ["src/**/*.py"],
                 "description": f"Implement the {feature.title} feature."},
                {"title": "Add unit tests", "file_patterns": ["tests/**/*.py"],
                 "description": "Add unit tests for the new feature."},
            ],
            estimated_risk="medium",
            raw_output="[STUB] Real planning logic in Plan 3",
        )

        await self._transition_to(db, feature, FeatureStatus.PLANNING.value)
        await self._write_execution(
            db, feature, ExecutionStage.PLANNING, ExecutionStatus.COMPLETED, result.to_dict(),
        )
        await notify_stage_completed(feature.id, ExecutionStage.PLANNING.value, result.to_dict())

    async def _run_implementing(self, db: AsyncSession, feature: Feature) -> None:
        logger.info("Stage implementing started for Feature %s", feature.id)
        await self._transition_to(db, feature, FeatureStatus.IMPLEMENTING.value)

        project = await self._load_project(db, feature.project_id)
        worktree_path = feature.worktree_path or f"/tmp/solo100/worktrees/{feature.id}"
        branch_name = feature.branch or f"feat/{feature.id[:8]}-{_slugify(feature.title)}"

        await self._git.create_branch(repo_path="/tmp/solo100/repos/test", branch_name=branch_name)
        await self._git.create_worktree(
            repo_path="/tmp/solo100/repos/test", branch_name=branch_name, worktree_path=worktree_path,
        )

        result = ImplementResult(
            files_changed=["src/example.py"],
            summary=f"[STUB] Implemented {feature.title}",
            commit_hash="stub_commit_abc123",
        )

        await self._write_execution(
            db, feature, ExecutionStage.IMPLEMENTING, ExecutionStatus.COMPLETED, result.to_dict(),
        )
        await notify_stage_completed(feature.id, ExecutionStage.IMPLEMENTING.value, result.to_dict())

    async def _run_testing(self, db: AsyncSession, feature: Feature) -> TestResult:
        logger.info("Stage testing started for Feature %s", feature.id)

        result = TestResult(
            passed=True, report="[STUB] All tests passed",
            passed_count=5, failed_count=0, duration_seconds=1.0,
        )

        await self._write_execution(
            db, feature, ExecutionStage.TESTING,
            ExecutionStatus.COMPLETED if result.passed else ExecutionStatus.FAILED,
            result.to_dict(),
        )
        await notify_stage_completed(feature.id, ExecutionStage.TESTING.value, result.to_dict())
        return result

    async def _run_reviewing(self, db: AsyncSession, feature: Feature) -> None:
        logger.info("Stage reviewing started for Feature %s", feature.id)

        report_result = await self._review_engine.review(feature, self._git)

        await self._write_execution(
            db, feature, ExecutionStage.REVIEWING, ExecutionStatus.COMPLETED,
            {"summary": report_result.summary, "issues": [asdict(i) for i in report_result.issues]},
        )
        await notify_stage_completed(feature.id, ExecutionStage.REVIEWING.value)

    async def _run_verifying(self, db: AsyncSession, feature: Feature) -> VerificationResult:
        logger.info("Stage verifying started for Feature %s", feature.id)

        worktree_path = feature.worktree_path or f"/tmp/solo100/worktrees/{feature.id}"

        rebase_result = await self._git.rebase(worktree_path, base_branch="main")
        if not rebase_result.success:
            result = VerificationResult(
                passed=False, test_passed=False, conflicts=rebase_result.conflicts,
                error_message=f"Rebase conflict in {len(rebase_result.conflicts)} file(s)",
            )
            await self._write_execution(
                db, feature, ExecutionStage.VERIFYING, ExecutionStatus.FAILED, result.to_dict(),
            )
            return result

        pr_result = await self._git.create_pr(
            branch=feature.branch or "main",
            title=f"feat: {feature.title}",
            body=f"Feature: {feature.title}\n\n{feature.description}",
            repo_url="https://github.com/stub/repo",
        )
        merge_result = await self._git.merge_pr(pr_result.pr_url)

        result = VerificationResult(
            passed=merge_result.success, test_passed=True,
            merge_url=pr_result.pr_url if merge_result.success else None,
            conflicts=[], error_message=None if merge_result.success else "Merge failed",
        )

        await self._write_execution(
            db, feature, ExecutionStage.VERIFYING,
            ExecutionStatus.COMPLETED if result.passed else ExecutionStatus.FAILED,
            result.to_dict(),
        )
        await notify_stage_completed(feature.id, ExecutionStage.VERIFYING.value, result.to_dict())
        return result

    # ── State transition helpers ──────────────────────────────────────────

    async def _transition_to(self, db: AsyncSession, feature: Feature, new_status: str) -> None:
        old_status = feature.status
        feature.status = new_status
        await db.execute(
            update(Feature).where(Feature.id == feature.id)
            .values(status=new_status, updated_at=func.now())
        )
        await db.flush()
        logger.info("Feature %s transitioned: %s → %s", feature.id, old_status, new_status)
        await notify_status_changed(feature.id, old_status, new_status)

    async def _set_failed(self, db: AsyncSession, feature_id: str, reason: str) -> None:
        await db.execute(
            update(Feature).where(Feature.id == feature_id)
            .values(status=FeatureStatus.FAILED.value, updated_at=func.now())
        )
        await db.flush()
        await notify_error(feature_id, "pipeline", f"Feature failed: {reason}")

    # ── Wait-for-approval loop ────────────────────────────────────────────

    async def _wait_for_approval(self, db: AsyncSession, feature: Feature, stage: str) -> None:
        await notify_awaiting_approval(
            feature.id, stage, f"Waiting for human approval at stage '{stage}'",
        )
        await db.commit()

        for _cycle in range(self._max_wait_cycles):
            await asyncio.sleep(self._poll_interval)

            refreshed = await self._load_feature_for_update(db, feature.id)
            if refreshed is None:
                raise FeatureExecutorError(f"Feature {feature.id} disappeared during wait")

            current = refreshed.status

            waiting_statuses = {
                ExecutionStage.BRAINSTORMING.value: [FeatureStatus.PLANNING.value, FeatureStatus.BRAINSTORMING.value],
                ExecutionStage.PLANNING.value: [FeatureStatus.IMPLEMENTING.value, FeatureStatus.BRAINSTORMING.value],
                ExecutionStage.TESTING.value: [FeatureStatus.REVIEWING.value, FeatureStatus.BRAINSTORMING.value],
                ExecutionStage.REVIEWING.value: [FeatureStatus.APPROVED.value, FeatureStatus.BRAINSTORMING.value],
            }

            valid_next = waiting_statuses.get(stage, [])
            if current in valid_next or current == FeatureStatus.FAILED.value:
                logger.info("Approval received for Feature %s stage %s: new status=%s",
                            feature.id, stage, current)
                return

            await db.commit()

        raise ApprovalTimeout(
            f"Approval timeout after {self._max_wait_cycles * self._poll_interval}s "
            f"for feature {feature.id} at stage '{stage}'"
        )

    # ── Database helpers ──────────────────────────────────────────────────

    async def _load_feature(self, db: AsyncSession, feature_id: str) -> Feature:
        result = await db.execute(select(Feature).where(Feature.id == feature_id))
        feature = result.scalar_one_or_none()
        if feature is None:
            raise FeatureExecutorError(f"Feature {feature_id} not found")
        return feature

    async def _load_feature_for_update(self, db: AsyncSession, feature_id: str) -> Feature | None:
        result = await db.execute(
            select(Feature).where(Feature.id == feature_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def _load_project(self, db: AsyncSession, project_id: str) -> Project | None:
        result = await db.execute(select(Project).where(Project.id == project_id))
        return result.scalar_one_or_none()

    async def _latest_execution(
        self, db: AsyncSession, feature_id: str, stage: str
    ) -> FeatureExecution | None:
        result = await db.execute(
            select(FeatureExecution)
            .where(FeatureExecution.feature_id == feature_id)
            .where(FeatureExecution.stage == stage)
            .order_by(FeatureExecution.started_at.desc())
        )
        return result.scalars().first()

    async def _write_execution(
        self, db: AsyncSession, feature: Feature,
        stage: ExecutionStage, status: ExecutionStatus,
        result_data: dict, attempt_number: int | None = None,
    ) -> FeatureExecution:
        from datetime import datetime, timezone

        if attempt_number is None:
            latest = await self._latest_execution(db, feature.id, stage.value)
            attempt_number = (latest.attempt_number if latest else 0) + 1

        execution = FeatureExecution(
            id=str(uuid.uuid4()),
            feature_id=feature.id,
            attempt_number=attempt_number,
            stage=stage.value,
            status=status.value,
            result_json=json.dumps(result_data),
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        await db.flush()
        return execution
