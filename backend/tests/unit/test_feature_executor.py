"""Unit tests for FeatureExecutor state machine."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.feature import Feature, FeatureStatus
from app.models.feature_execution import ExecutionStage, ExecutionStatus, FeatureExecution
from app.models.project import Project
from app.services.feature_executor import (
    ApprovalTimeout,
    FeatureExecutor,
    FeatureExecutorError,
    _slugify,
)


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
_test_engine = create_async_engine(TEST_DB_URL, echo=False)
_TestSessionFactory = async_sessionmaker(
    bind=_test_engine, class_=AsyncSession,
    expire_on_commit=False, autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with _TestSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> Project:
    proj = Project(
        id=str(uuid.uuid4()), name="Test Project",
        ssh_url="git@github.com:test/repo.git",
        default_branch="main", ssh_key_env="SSH_KEY_TEST",
    )
    db_session.add(proj)
    await db_session.flush()
    await db_session.commit()
    return proj


@pytest_asyncio.fixture
async def feature(db_session: AsyncSession, project: Project) -> Feature:
    feat = Feature(
        id=str(uuid.uuid4()), project_id=project.id,
        title="Add user authentication",
        description="Implement login and logout functionality.",
        status=FeatureStatus.PENDING.value,
    )
    db_session.add(feat)
    await db_session.flush()
    await db_session.commit()
    return feat


class TestSlugify:
    def test_removes_special_chars(self) -> None:
        assert _slugify("Hello, World!") == "hello-world"

    def test_collapse_whitespace(self) -> None:
        assert _slugify("add  user   auth") == "add-user-auth"

    def test_truncates_long_titles(self) -> None:
        assert len(_slugify("a" * 100)) <= 64

    def test_strips_leading_trailing_dashes(self) -> None:
        assert _slugify("  hello  ") == "hello"


class TestExecutorInstantiation:
    def test_default_git_manager(self) -> None:
        executor = FeatureExecutor()
        assert executor._git is not None

    def test_custom_git_manager(self) -> None:
        mock_git = MagicMock()
        executor = FeatureExecutor(git_manager=mock_git)
        assert executor._git is mock_git

    def test_custom_poll_intervals(self) -> None:
        executor = FeatureExecutor(poll_interval=10, max_wait_cycles=5)
        assert executor._poll_interval == 10
        assert executor._max_wait_cycles == 5


class TestExecutorDatabaseHelpers:
    @pytest.mark.asyncio
    async def test_load_feature_raises_on_not_found(self, db_session: AsyncSession) -> None:
        executor = FeatureExecutor()
        with pytest.raises(FeatureExecutorError, match="not found"):
            await executor._load_feature(db_session, str(uuid.uuid4()))

    @pytest.mark.asyncio
    async def test_load_feature_returns_feature(self, db_session: AsyncSession, feature: Feature) -> None:
        executor = FeatureExecutor()
        loaded = await executor._load_feature(db_session, feature.id)
        assert loaded.id == feature.id
        assert loaded.title == "Add user authentication"

    @pytest.mark.asyncio
    async def test_write_execution_creates_record(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        executor = FeatureExecutor()
        result_data = {"analysis": "test analysis", "acceptance_criteria": ["AC1"]}

        execution = await executor._write_execution(
            db_session, feature,
            ExecutionStage.BRAINSTORMING, ExecutionStatus.COMPLETED,
            result_data,
        )

        assert execution.id is not None
        assert execution.feature_id == feature.id
        assert execution.stage == "brainstorming"
        assert execution.status == "completed"
        assert json.loads(execution.result_json or "{}") == result_data


class TestExecutorTransitionTo:
    @pytest.mark.asyncio
    async def test_transition_updates_status(self, db_session: AsyncSession, feature: Feature) -> None:
        executor = FeatureExecutor()
        await executor._transition_to(db_session, feature, FeatureStatus.BRAINSTORMING.value)
        await db_session.flush()

        # Re-load from DB to verify persisted status (avoid expired attribute)
        reloaded = await executor._load_feature(db_session, feature.id)
        assert reloaded.status == FeatureStatus.BRAINSTORMING.value


class TestExecutorBrainstormingStage:
    @pytest.mark.asyncio
    async def test_run_brainstorming_writes_execution(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        # Mock Agent to avoid calling real Claude Code CLI
        from app.services.stage_results import BrainstormResult

        mock_agent = MagicMock()
        mock_agent.brainstorm = AsyncMock(return_value=BrainstormResult(
            analysis="Mock analysis",
            acceptance_criteria=["criteria1", "criteria2"],
            key_points=["point1"],
            estimated_risk="low",
        ))

        executor = FeatureExecutor()
        executor._agent = mock_agent

        await executor._transition_to(db_session, feature, FeatureStatus.BRAINSTORMING.value)
        await executor._run_brainstorming(db_session, feature)
        await db_session.flush()

        executions = await db_session.execute(
            select(FeatureExecution).where(
                FeatureExecution.feature_id == feature.id,
                FeatureExecution.stage == ExecutionStage.BRAINSTORMING.value,
            )
        )
        exec_records = executions.scalars().all()
        assert len(exec_records) >= 1

        latest = exec_records[-1]
        assert latest.status == ExecutionStatus.COMPLETED.value
        result = json.loads(latest.result_json or "{}")
        assert "analysis" in result
        assert "acceptance_criteria" in result


class TestExecutorPlanningStage:
    @pytest.mark.asyncio
    async def test_run_planning_writes_execution(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        from app.services.stage_results import Plan

        # 先写入 brainstorming 执行记录，供 planning 阶段读取
        executor = FeatureExecutor()
        await executor._write_execution(
            db_session, feature,
            ExecutionStage.BRAINSTORMING, ExecutionStatus.COMPLETED,
            {"analysis": "mock analysis", "acceptance_criteria": ["AC1"], "key_points": [], "estimated_risk": "low"},
        )
        await db_session.flush()

        mock_agent = MagicMock()
        mock_agent.plan = AsyncMock(return_value=Plan(
            tasks=[{"title": "task1", "description": "d", "files": ["a.py"]}],
            estimated_risk="low",
            raw_output="mock plan",
        ))
        executor._agent = mock_agent

        await executor._run_planning(db_session, feature)
        await db_session.flush()

        executions = await db_session.execute(
            select(FeatureExecution).where(
                FeatureExecution.feature_id == feature.id,
                FeatureExecution.stage == ExecutionStage.PLANNING.value,
            )
        )
        record = executions.scalar_one_or_none()
        assert record is not None
        assert record.status == ExecutionStatus.COMPLETED.value
        result = json.loads(record.result_json or "{}")
        assert "tasks" in result
        assert len(result["tasks"]) == 1

    @pytest.mark.asyncio
    async def test_run_planning_transitions_to_planning_status(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        from app.services.stage_results import Plan

        executor = FeatureExecutor()
        await executor._write_execution(
            db_session, feature,
            ExecutionStage.BRAINSTORMING, ExecutionStatus.COMPLETED,
            {"analysis": "a", "acceptance_criteria": [], "key_points": [], "estimated_risk": "low"},
        )
        await db_session.flush()

        mock_agent = MagicMock()
        mock_agent.plan = AsyncMock(return_value=Plan(
            tasks=[{"title": "t", "description": "d", "files": []}],
            estimated_risk="low",
            raw_output="",
        ))
        executor._agent = mock_agent

        await executor._run_planning(db_session, feature)
        await db_session.flush()

        reloaded = await executor._load_feature(db_session, feature.id)
        assert reloaded.status == FeatureStatus.PLANNING.value


class TestExecutorTestingStage:
    @pytest.mark.asyncio
    async def test_run_testing_stub_returns_passed(self, db_session: AsyncSession, feature: Feature) -> None:
        executor = FeatureExecutor()
        result = await executor._run_testing(db_session, feature)
        assert result.passed is True
        assert result.failed_count == 0

    @pytest.mark.asyncio
    async def test_run_testing_writes_execution(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        executor = FeatureExecutor()
        await executor._run_testing(db_session, feature)
        await db_session.flush()

        exec_result = await db_session.execute(
            select(FeatureExecution).where(
                FeatureExecution.feature_id == feature.id,
                FeatureExecution.stage == ExecutionStage.TESTING.value,
            )
        )
        record = exec_result.scalar_one_or_none()
        assert record is not None
        assert record.status == ExecutionStatus.COMPLETED.value


class TestExecutorVerifyingStage:
    @pytest.mark.asyncio
    async def test_run_verifying_success(self, db_session: AsyncSession, feature: Feature) -> None:
        executor = FeatureExecutor()
        feature.worktree_path = "/tmp/test_worktree"
        feature.branch = "feat/test"
        db_session.add(feature)
        await db_session.flush()

        with patch.object(executor._git, "rebase", new_callable=AsyncMock) as mock_rebase, \
             patch.object(executor._git, "create_pr", new_callable=AsyncMock) as mock_pr, \
             patch.object(executor._git, "merge_pr", new_callable=AsyncMock) as mock_merge:
            mock_rebase.return_value = MagicMock(success=True, conflicts=[])
            mock_pr.return_value = MagicMock(pr_url="https://github.com/org/repo/pull/1")
            mock_merge.return_value = MagicMock(success=True)

            result = await executor._run_verifying(db_session, feature)

        assert result.passed is True
        assert result.merge_url == "https://github.com/org/repo/pull/1"

    @pytest.mark.asyncio
    async def test_run_verifying_rebase_conflict(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        executor = FeatureExecutor()
        feature.worktree_path = "/tmp/test_worktree"
        feature.branch = "feat/test"
        db_session.add(feature)
        await db_session.flush()

        with patch.object(executor._git, "rebase", new_callable=AsyncMock) as mock_rebase:
            mock_rebase.return_value = MagicMock(
                success=False, conflicts=["src/auth.py", "src/config.ts"]
            )
            result = await executor._run_verifying(db_session, feature)

        assert result.passed is False
        assert result.conflicts == ["src/auth.py", "src/config.ts"]
        assert "Rebase conflict" in (result.error_message or "")


class TestExecutorReviewingStage:
    @pytest.mark.asyncio
    async def test_run_reviewing_writes_execution(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        from app.services.review_engine import ReviewReportResult, ReviewIssue

        executor = FeatureExecutor()
        mock_review_engine = MagicMock()
        mock_review_engine.review = AsyncMock(return_value=ReviewReportResult(
            summary="Code looks good",
            issues=[],
            ai_raw="",
        ))
        executor._review_engine = mock_review_engine

        await executor._run_reviewing(db_session, feature)
        await db_session.flush()

        executions = await db_session.execute(
            select(FeatureExecution).where(
                FeatureExecution.feature_id == feature.id,
                FeatureExecution.stage == ExecutionStage.REVIEWING.value,
            )
        )
        record = executions.scalar_one_or_none()
        assert record is not None
        assert record.status == ExecutionStatus.COMPLETED.value
        result = json.loads(record.result_json or "{}")
        assert result["summary"] == "Code looks good"
        assert result["issues"] == []

    @pytest.mark.asyncio
    async def test_run_reviewing_records_issues(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        from app.services.review_engine import ReviewReportResult, ReviewIssue

        executor = FeatureExecutor()
        mock_review_engine = MagicMock()
        mock_review_engine.review = AsyncMock(return_value=ReviewReportResult(
            summary="Found issues",
            issues=[
                ReviewIssue(severity="warning", file="src/auth.py", line=10, description="Missing validation"),
            ],
            ai_raw="",
        ))
        executor._review_engine = mock_review_engine

        await executor._run_reviewing(db_session, feature)
        await db_session.flush()

        executions = await db_session.execute(
            select(FeatureExecution).where(
                FeatureExecution.feature_id == feature.id,
                FeatureExecution.stage == ExecutionStage.REVIEWING.value,
            )
        )
        record = executions.scalar_one_or_none()
        result = json.loads(record.result_json or "{}")
        assert len(result["issues"]) == 1
        assert result["issues"][0]["severity"] == "warning"
        assert result["issues"][0]["file"] == "src/auth.py"


class TestExecutorRunPipeline:
    @pytest.mark.asyncio
    async def test_rejects_invalid_start_status(
        self, db_session: AsyncSession, feature: Feature
    ) -> None:
        feature.status = FeatureStatus.IMPLEMENTING.value
        db_session.add(feature)
        await db_session.flush()
        await db_session.commit()

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_db_context():
            yield db_session

        executor = FeatureExecutor()
        with patch("app.services.feature_executor.get_db_context", mock_get_db_context):
            result = await executor.run_pipeline(feature.id)

        assert result["success"] is False
        assert "cannot start pipeline" in result["error"]
