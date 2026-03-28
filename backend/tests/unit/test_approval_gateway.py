"""Unit tests for ApprovalGateway."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.feature import Feature, FeatureStatus
from app.models.feature_execution import FeatureExecution
from app.models.project import Project
from app.services.approval_gateway import ApprovalGateway, InvalidActionError


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
async def pending_feature(db_session: AsyncSession) -> Feature:
    proj = Project(
        id=str(uuid.uuid4()), name="Test Project",
        ssh_url="git@github.com:test/repo.git",
        default_branch="main", ssh_key_env="SSH_KEY",
    )
    db_session.add(proj)
    await db_session.flush()

    feat = Feature(
        id=str(uuid.uuid4()), project_id=proj.id,
        title="Test Feature", description="Test description",
        status=FeatureStatus.PENDING.value, retry_count=0, max_retries=3,
    )
    db_session.add(feat)
    await db_session.flush()
    return feat


class TestApprovalGatewayTransitions:

    @pytest.mark.asyncio
    async def test_approve_brainstorming_moves_to_planning(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.BRAINSTORMING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "approve")
        assert result.status == FeatureStatus.PLANNING.value

    @pytest.mark.asyncio
    async def test_reject_brainstorming_increments_retry(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.BRAINSTORMING.value
        pending_feature.retry_count = 0
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "reject")
        assert result.status == FeatureStatus.BRAINSTORMING.value
        assert result.retry_count == 1

    @pytest.mark.asyncio
    async def test_approve_planning_moves_to_implementing(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.PLANNING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "approve")
        assert result.status == FeatureStatus.IMPLEMENTING.value

    @pytest.mark.asyncio
    async def test_reject_planning_moves_to_brainstorming(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.PLANNING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "reject")
        assert result.status == FeatureStatus.BRAINSTORMING.value

    @pytest.mark.asyncio
    async def test_approve_testing_moves_to_reviewing(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.TESTING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "approve")
        assert result.status == FeatureStatus.REVIEWING.value

    @pytest.mark.asyncio
    async def test_ignore_test_failure_moves_to_reviewing(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.TESTING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "ignore_test_failure")
        assert result.status == FeatureStatus.REVIEWING.value

    @pytest.mark.asyncio
    async def test_approve_reviewing_moves_to_approved(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.REVIEWING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "approve")
        assert result.status == FeatureStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_reject_reviewing_moves_to_brainstorming(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.REVIEWING.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "reject")
        assert result.status == FeatureStatus.BRAINSTORMING.value

    @pytest.mark.asyncio
    async def test_retry_verification_from_approved(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.APPROVED.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "retry_verification")
        assert result.status == FeatureStatus.VERIFYING.value


class TestApprovalGatewayInvalidActions:

    @pytest.mark.asyncio
    async def test_approve_pending_is_invalid(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        gateway = ApprovalGateway()
        with pytest.raises(InvalidActionError):
            await gateway.handle(db_session, pending_feature.id, "approve")

    @pytest.mark.asyncio
    async def test_approve_merged_is_invalid(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.MERGED.value
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        with pytest.raises(InvalidActionError):
            await gateway.handle(db_session, pending_feature.id, "approve")

    @pytest.mark.asyncio
    async def test_feature_not_found(self, db_session: AsyncSession) -> None:
        gateway = ApprovalGateway()
        with pytest.raises(InvalidActionError, match="not found"):
            await gateway.handle(db_session, str(uuid.uuid4()), "approve")


class TestApprovalGatewayRetryLimit:

    @pytest.mark.asyncio
    async def test_reject_at_max_retries_moves_to_failed(
        self, db_session: AsyncSession, pending_feature: Feature
    ) -> None:
        pending_feature.status = FeatureStatus.BRAINSTORMING.value
        pending_feature.retry_count = 2  # max_retries=3, next reject → 3 → failed
        db_session.add(pending_feature)
        await db_session.flush()

        gateway = ApprovalGateway()
        result = await gateway.handle(db_session, pending_feature.id, "reject")
        assert result.status == FeatureStatus.FAILED.value
        assert result.retry_count == 3
