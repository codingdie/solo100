# solo100 后端基础层实现计划

**文档路径**: `docs/superpowers/plans/2026-03-26-plan-1-backend-foundation.md`
**版本**: v0.1 Backend Foundation
**日期**: 2026-03-26

---

## Goal

搭建 solo100 后端基础层，实现从项目脚手架到完整 REST API 的所有基础设施，为后续 Feature Executor、Agent、Celery 等业务逻辑层的接入奠定根基。

---

## Architecture

```
solo100/
├── docker-compose.yml          # 编排 backend + redis
├── .env.example                # 环境变量模板
└── backend/
    ├── app/
    │   ├── main.py             # FastAPI 入口
    │   ├── config.py           # Pydantic Settings 配置
    │   ├── database.py         # SQLAlchemy async engine + session
    │   ├── models/            # 5 个 SQLAlchemy ORM 模型
    │   ├── schemas/           # Pydantic 请求/响应模型
    │   └── routers/           # 5 个 API 路由文件
    └── tests/
        └── unit/              # 每个模型的 CRUD 测试
```

数据库：SQLite（文件），由 Alembic 管理迁移。
异步 Runtime：FastAPI + uvicorn（ASGI），使用 `async def` 风格的 SQLAlchemy 2.0 async session。
状态机操作（start/archive/reset/approve/reject/ignore-test-failure/retry-verification）本次仅注册路由并返回 501，业务逻辑在后续迭代中实现。

---

## Tech Stack

| 组件 | 技术 |
|------|------|
| Web Framework | FastAPI 0.109+ |
| ORM | SQLAlchemy 2.0 (async, aiosqlite) |
| Validation | Pydantic v2 (BaseModel, Settings) |
| Migrations | Alembic (async support) |
| Task Queue | Celery 5 + Redis |
| Server | uvicorn (ASGI) |
| Testing | pytest, pytest-asyncio |
| DB | SQLite |

---

## 前置依赖

在开始 Task 1 之前，确保工作目录干净：

```bash
git status
```

所有文件创建均在 `/home/codingdie/codes/solo100/` 根目录下进行。

---

## Task 1: 项目脚手架

**Files**
- 创建: `backend/requirements.txt`
- 创建: `backend/Dockerfile`
- 创建: `docker-compose.yml`
- 创建: `.env.example`

### 步骤 1.1 创建目录结构

```bash
mkdir -p backend/app/models backend/app/schemas backend/app/routers
mkdir -p backend/app/services backend/app/agents backend/app/tasks
mkdir -p backend/tests/unit
mkdir -p backend/alembic/versions
mkdir -p docs/superpowers/plans
```

### 步骤 1.2 创建 `backend/requirements.txt`

```
# Core
fastapi==0.109.2
uvicorn[standard]==0.27.1
pydantic==2.6.1
pydantic-settings==2.2.1

# Database
sqlalchemy[asyncio]==2.0.27
aiosqlite==0.19.0
alembic==1.13.1

# Task Queue
celery[redis]==5.3.6
redis==5.0.1

# HTTP client (for WebSocket relay / feishu webhook)
httpx==0.26.0

# Testing
pytest==8.0.1
pytest-asyncio==0.23.5
pytest-cov==4.1.0
httpx==0.26.0

# Utilities
python-dotenv==1.0.1
python-multipart==0.0.9
```

### 步骤 1.3 创建 `backend/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Celery worker ( CMD is overridden by docker-compose )
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 步骤 1.4 创建 `docker-compose.yml`

```yaml
version: "3.9"

services:
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./backend:/app
    depends_on:
      - redis
    networks:
      - solo100

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - solo100

networks:
  solo100:
    driver: bridge
```

### 步骤 1.5 创建 `.env.example`

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./solo100.db

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Feishu (optional)
FEISHU_WEBHOOK_URL=

# SSH key env var name template (actual key stored in this env var at runtime)
# Each project references its key via an env-var name, e.g. SSH_KEY_PROJECT_1
SSH_KEY_PROJECT_DEFAULT=SSH_KEY_PROJECT_DEFAULT

# Claude Code
ANTHROPIC_API_KEY_ENV=ANTHROPIC_API_KEY

# App
APP_ENV=development
LOG_LEVEL=INFO
```

**Commit:**

```bash
git add backend/requirements.txt backend/Dockerfile docker-compose.yml .env.example
git commit -m "chore: add backend scaffolding with requirements.txt, Dockerfile and docker-compose

添加后端基础脚手架：requirements.txt（FastAPI/SQLAlchemy/Celery）、backend/Dockerfile、
docker-compose.yml（backend + redis 服务编排）、.env.example 环境变量模板
"
```

---

## Task 2: 数据库配置与 Alembic 迁移

**Files**
- 创建: `backend/app/config.py`
- 创建: `backend/app/database.py`
- 创建: `backend/alembic.ini`
- 创建: `backend/alembic/env.py`
- 创建: `backend/alembic/script.py.mako`
- 创建: `backend/alembic/versions/001_initial.py`

### 步骤 2.1 创建 `backend/app/config.py`

```python
"""Application configuration loaded from environment variables.

Loads settings via Pydantic Settings so all config lives in .env files.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./solo100.db"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Feishu (optional)
    feishu_webhook_url: str = ""

    # SSH keys
    ssh_key_project_default: str = "SSH_KEY_PROJECT_DEFAULT"

    # Claude Code / AI
    anthropic_api_key_env: str = "ANTHROPIC_API_KEY"

    # App
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
```

### 步骤 2.2 创建 `backend/app/database.py`

```python
"""SQLAlchemy async engine and session factory.

Provides a shared AsyncSessionLocal that can be imported anywhere in the app.
All sessions are managed via context managers (async with) to ensure proper cleanup.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Standalone context manager for use outside of FastAPI request context."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### 步骤 2.3 初始化 Alembic

```bash
cd /home/codingdie/codes/solo100/backend && \
  pip install alembic==1.13.1 --quiet && \
  alembic init alembic --template generic
```

初始化后调整 `alembic.ini` 中的 `sqlalchemy.url`：

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite+aiosqlite:///./solo100.db
```

### 步骤 2.4 更新 `backend/alembic/env.py`

```python
"""Alembic async migration environment."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings
from app.database import Base

# Import all models so Base.metadata sees them
from app.models import (
    agent_config,
    feature,
    feature_execution,
    project,
    review_report,
)

config = context.config

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+aiosqlite", ""))


if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


async def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    asyncio.run(run_migrations_offline())
else:
    asyncio.run(run_migrations_online())
```

### 步骤 2.5 创建初始迁移文件 `backend/alembic/versions/001_initial.py`

```python
"""Initial migration: create all v0.1 tables.

Revision ID: 001
Revises:
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # project
    op.create_table(
        "project",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ssh_url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.Text(), nullable=False, server_default="main"),
        sa.Column("ssh_key_env", sa.Text(), nullable=False),
        sa.Column("default_agent_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # agent_config
    op.create_table(
        "agent_config",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False, server_default="claude_code"),
        sa.Column("api_key_env", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    # feature
    op.create_table(
        "feature",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("branch", sa.Text(), nullable=True),
        sa.Column("pr_url", sa.Text(), nullable=True),
        sa.Column("worktree_path", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # feature_execution
    op.create_table(
        "feature_execution",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("feature_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["feature_id"], ["feature.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # review_report
    op.create_table(
        "review_report",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("feature_id", sa.Text(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("ai_issues_json", sa.Text(), nullable=True),
        sa.Column("human_decision", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["feature_id"], ["feature.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("review_report")
    op.drop_table("feature_execution")
    op.drop_table("feature")
    op.drop_table("agent_config")
    op.drop_table("project")
```

**Commit:**

```bash
git add backend/app/config.py backend/app/database.py backend/alembic.ini \
         backend/alembic/env.py backend/alembic/script.py.mako \
         backend/alembic/versions/001_initial.py
git commit -m "feat: add database config, Alembic setup and initial migration

添加 app/config.py（Pydantic Settings）、app/database.py（SQLAlchemy async engine +
AsyncSessionLocal + get_db dependency）、Alembic 初始化配置和 001_initial 迁移脚本，
包含 project/feature/feature_execution/review_report/agent_config 五张表
"
```

---

## Task 3: ORM 模型

**Files**
- 创建: `backend/app/models/__init__.py`
- 创建: `backend/app/models/project.py`
- 创建: `backend/app/models/feature.py`
- 创建: `backend/app/models/feature_execution.py`
- 创建: `backend/app/models/review_report.py`
- 创建: `backend/app/models/agent_config.py`

### 步骤 3.1 创建 `backend/app/models/__init__.py`

```python
"""SQLAlchemy ORM models."""

from app.models.agent_config import AgentConfig
from app.models.feature import Feature
from app.models.feature_execution import FeatureExecution
from app.models.project import Project
from app.models.review_report import ReviewReport

__all__ = [
    "Project",
    "Feature",
    "FeatureExecution",
    "ReviewReport",
    "AgentConfig",
]
```

### 步骤 3.2 创建 `backend/app/models/project.py`

```python
"""Project ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    """A Git repository project that hosts Features."""

    __tablename__ = "project"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ssh_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default="main",
    )
    ssh_key_env: Mapped[str] = mapped_column(String(255), nullable=False)
    # Name of the env var that holds the SSH private key, e.g. SSH_KEY_PROJECT_1
    default_agent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_config.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    features: Mapped[list["Feature"]] = relationship(
        "Feature",
        back_populates="project",
        cascade="all, delete-orphan",
    )
    default_agent: Mapped["AgentConfig | None"] = relationship(
        "AgentConfig",
        foreign_keys=[default_agent_id],
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name})>"
```

### 步骤 3.3 创建 `backend/app/models/feature.py`

```python
"""Feature ORM model and status enum."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FeatureStatus(str, Enum):
    """All possible states of a Feature."""

    PENDING = "pending"
    BRAINSTORMING = "brainstorming"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    VERIFYING = "verifying"
    MERGED = "merged"
    FAILED = "failed"
    ARCHIVED = "archived"


class Feature(Base):
    """A single Feature (user story / task) under a Project."""

    __tablename__ = "feature"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=FeatureStatus.PENDING.value,
    )
    branch: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # e.g. feat/<id-prefix>-<title-slug>
    pr_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    worktree_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="3",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="features")
    executions: Mapped[list["FeatureExecution"]] = relationship(
        "FeatureExecution",
        back_populates="feature",
        cascade="all, delete-orphan",
        order_by="FeatureExecution.started_at",
    )
    review_reports: Mapped[list["ReviewReport"]] = relationship(
        "ReviewReport",
        back_populates="feature",
        cascade="all, delete-orphan",
        order_by="ReviewReport.created_at",
    )

    def __repr__(self) -> str:
        return f"<Feature(id={self.id}, title={self.title}, status={self.status})>"
```

### 步骤 3.4 创建 `backend/app/models/feature_execution.py`

```python
"""FeatureExecution ORM model and stage enum."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ExecutionStage(str, Enum):
    """Stages that produce a FeatureExecution record."""

    BRAINSTORMING = "brainstorming"
    PLANNING = "planning"
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    REVIEWING = "reviewing"
    VERIFYING = "verifying"


class ExecutionStatus(str, Enum):
    """Status of a FeatureExecution record."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FeatureExecution(Base):
    """Record of a single stage execution within a Feature attempt."""

    __tablename__ = "feature_execution"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    feature_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("feature.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    feature: Mapped["Feature"] = relationship(
        "Feature",
        back_populates="executions",
    )

    def __repr__(self) -> str:
        return (
            f"<FeatureExecution(id={self.id}, feature_id={self.feature_id}, "
            f"stage={self.stage}, status={self.status})>"
        )
```

### 步骤 3.5 创建 `backend/app/models/review_report.py`

```python
"""ReviewReport ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewReport(Base):
    """AI code review report for a Feature attempt."""

    __tablename__ = "review_report"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    feature_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("feature.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_issues_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    human_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # "approve" | "reject", filled when human makes a decision
    decided_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # Relationships
    feature: Mapped["Feature"] = relationship(
        "Feature",
        back_populates="review_reports",
    )

    def __repr__(self) -> str:
        return (
            f"<ReviewReport(id={self.id}, feature_id={self.feature_id}, "
            f"human_decision={self.human_decision})>"
        )
```

### 步骤 3.6 创建 `backend/app/models/agent_config.py`

```python
"""AgentConfig ORM model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentConfig(Base):
    """Configuration for a specific AI Agent (Claude Code, Codex, etc.)."""

    __tablename__ = "agent_config"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default="claude_code",
    )
    api_key_env: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    # Name of the env var that holds the API key, e.g. ANTHROPIC_API_KEY
    is_default: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<AgentConfig(id={self.id}, name={self.name}, type={self.type})>"
```

**Commit:**

```bash
git add backend/app/models/__init__.py \
         backend/app/models/project.py \
         backend/app/models/feature.py \
         backend/app/models/feature_execution.py \
         backend/app/models/review_report.py \
         backend/app/models/agent_config.py
git commit -m "feat: add all five SQLAlchemy ORM models

添加 project.py、feature.py（包含 FeatureStatus 枚举）、feature_execution.py（包含
ExecutionStage/ExecutionStatus 枚举）、review_report.py、agent_config.py，完整对应
数据模型设计文档
"
```

---

## Task 4: Pydantic Schemas

**Files**
- 创建: `backend/app/schemas/__init__.py`
- 创建: `backend/app/schemas/project.py`
- 创建: `backend/app/schemas/feature.py`
- 创建: `backend/app/schemas/agent.py`

### 步骤 4.1 创建 `backend/app/schemas/__init__.py`

```python
"""Pydantic schemas for API request/response validation."""

from app.schemas.agent import (
    AgentConfigCreate,
    AgentConfigResponse,
    AgentConfigUpdate,
)
from app.schemas.feature import (
    FeatureCreate,
    FeatureExecutionResponse,
    FeatureResponse,
    FeatureReviewResponse,
    FeatureUpdate,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
)

__all__ = [
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    # Feature
    "FeatureCreate",
    "FeatureUpdate",
    "FeatureResponse",
    "FeatureExecutionResponse",
    "FeatureReviewResponse",
    # Agent
    "AgentConfigCreate",
    "AgentConfigUpdate",
    "AgentConfigResponse",
]
```

### 步骤 4.2 创建 `backend/app/schemas/project.py`

```python
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
```

### 步骤 4.3 创建 `backend/app/schemas/feature.py`

```python
"""Pydantic schemas for Feature and related resources."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------
# Feature
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# FeatureExecution
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# ReviewReport
# ------------------------------------------------------------------


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
```

### 步骤 4.4 创建 `backend/app/schemas/agent.py`

```python
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
```

**Commit:**

```bash
git add backend/app/schemas/__init__.py \
         backend/app/schemas/project.py \
         backend/app/schemas/feature.py \
         backend/app/schemas/agent.py
git commit -m "feat: add all Pydantic schemas for API validation

添加 project.py、feature.py（Feature + FeatureExecution + ReviewReport）、agent.py
三个 schema 模块，提供完整的请求验证和响应序列化
"
```

---

## Task 5: REST API 路由

**Files**
- 创建: `backend/app/routers/__init__.py`
- 创建: `backend/app/routers/projects.py`
- 创建: `backend/app/routers/features.py`
- 创建: `backend/app/routers/approvals.py`
- 创建: `backend/app/routers/agents.py`
- 创建: `backend/app/routers/websocket.py`

### 步骤 5.1 创建 `backend/app/routers/__init__.py`

```python
"""FastAPI router aggregation."""

from app.routers.agents import router as agents_router
from app.routers.approvals import router as approvals_router
from app.routers.features import router as features_router
from app.routers.projects import router as projects_router
from app.routers.websocket import router as websocket_router

__all__ = [
    "projects_router",
    "features_router",
    "approvals_router",
    "agents_router",
    "websocket_router",
]
```

### 步骤 5.2 创建 `backend/app/routers/projects.py`

```python
"""REST router for Project CRUD operations.

GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PUT    /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("", response_model=ProjectListResponse)
async def list_projects(db: AsyncSession = Depends(get_db)) -> ProjectListResponse:
    """Return all projects ordered by created_at desc."""
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    items = result.scalars().all()
    return ProjectListResponse(
        items=[ProjectResponse.model_validate(p) for p in items],
        total=len(items),
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project."""
    project = Project(
        name=payload.name,
        ssh_url=payload.ssh_url,
        default_branch=payload.default_branch,
        ssh_key_env=payload.ssh_key_env,
        default_agent_id=payload.default_agent_id,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Return a single project by id."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project (partial update)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project and all its Features."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.flush()
```

### 步骤 5.3 创建 `backend/app/routers/features.py`

```python
"""REST router for Feature CRUD and state-transition operations.

GET    /api/v1/projects/{project_id}/features
POST   /api/v1/projects/{project_id}/features
GET    /api/v1/features/{id}
POST   /api/v1/features/{id}/start
POST   /api/v1/features/{id}/archive
POST   /api/v1/features/{id}/reset
GET    /api/v1/features/{id}/executions
GET    /api/v1/features/{id}/review
"""

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


# ------------------------------------------------------------------
# Project-scoped Feature list / create
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Feature detail
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# State-machine operations (placeholder — business logic in later iterations)
# ------------------------------------------------------------------


@router.post("/features/{feature_id}/start", response_model=FeatureResponse)
async def start_feature(
    feature_id: str,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Transition a Feature from pending to brainstorming.

    Business logic (clone repo, create branch, enqueue Celery task)
    will be implemented in a future iteration.
    """
    result = await db.execute(select(Feature).where(Feature.id == feature_id))
    feature = result.scalar_one_or_none()
    if feature is None:
        raise HTTPException(status_code=404, detail="Feature not found")
    # TODO: implement state machine transition + Celery task dispatch
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
    # TODO: implement state machine + worktree cleanup
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
    # TODO: implement state machine + Celery task dispatch
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Feature reset logic not yet implemented",
    )


# ------------------------------------------------------------------
# Execution records
# ------------------------------------------------------------------


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


# ------------------------------------------------------------------
# Review report
# ------------------------------------------------------------------


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
```

### 步骤 5.4 创建 `backend/app/routers/approvals.py`

```python
"""REST router for human-intervention approval/rejection operations.

POST /api/v1/features/{id}/approve
POST /api/v1/features/{id}/reject
POST /api/v1/features/{id}/ignore-test-failure
POST /api/v1/features/{id}/retry-verification
"""

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
    """Generic approve: advance the Feature from any waiting state.

    Business logic (state machine transition + task signalling) to be
    implemented in a future iteration.
    """
    feature = await _get_feature_or_404(feature_id, db)
    # TODO: implement ApprovalGateway logic
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
    # TODO: implement ApprovalGateway logic
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
    # TODO: implement ApprovalGateway logic
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
    # TODO: implement ApprovalGateway logic
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Retry verification logic not yet implemented",
    )
```

### 步骤 5.5 创建 `backend/app/routers/agents.py`

```python
"""REST router for AgentConfig CRUD operations.

GET    /api/v1/agents
POST   /api/v1/agents
PUT    /api/v1/agents/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent_config import AgentConfig
from app.schemas.agent import (
    AgentConfigCreate,
    AgentConfigListResponse,
    AgentConfigResponse,
    AgentConfigUpdate,
)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("", response_model=AgentConfigListResponse)
async def list_agents(db: AsyncSession = Depends(get_db)) -> AgentConfigListResponse:
    """Return all agent configurations."""
    result = await db.execute(
        select(AgentConfig).order_by(AgentConfig.created_at.desc()),
    )
    items = result.scalars().all()
    return AgentConfigListResponse(
        items=[AgentConfigResponse.model_validate(a) for a in items],
        total=len(items),
    )


@router.post(
    "",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_agent(
    payload: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Create a new agent configuration.

    If is_default is True, unset is_default on all other agents.
    """
    if payload.is_default:
        result = await db.execute(
            select(AgentConfig).where(AgentConfig.is_default == 1),
        )
        for agent in result.scalars():
            agent.is_default = 0

    agent = AgentConfig(
        name=payload.name,
        type=payload.type,
        api_key_env=payload.api_key_env,
        is_default=1 if payload.is_default else 0,
    )
    db.add(agent)
    await db.flush()
    await db.refresh(agent)
    return AgentConfigResponse.model_validate(agent)


@router.put("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent(
    agent_id: str,
    payload: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> AgentConfigResponse:
    """Update an agent configuration (partial update)."""
    result = await db.execute(
        select(AgentConfig).where(AgentConfig.id == agent_id),
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "is_default" in update_data and update_data["is_default"]:
        other_result = await db.execute(
            select(AgentConfig).where(
                AgentConfig.is_default == 1,
                AgentConfig.id != agent_id,
            ),
        )
        for other in other_result.scalars():
            other.is_default = 0
        update_data["is_default"] = 1
    elif "is_default" in update_data:
        update_data["is_default"] = 0

    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.flush()
    await db.refresh(agent)
    return AgentConfigResponse.model_validate(agent)
```

### 步骤 5.6 创建 `backend/app/routers/websocket.py`

```python
"""WebSocket router for real-time Feature event push.

WS /ws/features/{feature_id}
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


# In-memory registry: feature_id -> list of active WebSocket connections
_active_connections: dict[str, list[WebSocket]] = {}


async def _accept(websocket: WebSocket) -> None:
    """Accept a WebSocket connection."""
    await websocket.accept()


async def _send_json(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Send a JSON-serialisable dict over a WebSocket."""
    await websocket.send_text(json.dumps(data, default=str))


@router.websocket("/ws/features/{feature_id}")
async def feature_websocket(websocket: WebSocket, feature_id: str) -> None:
    """Bidirectional WebSocket channel for a single Feature.

    Client connects and receives real-time push messages:
      - status_change
      - log
      - stage_complete
      - awaiting_approval
      - error

    Currently only registers the connection. Message relay via
    NotificationHub will be wired up when the service layer is built.
    """
    await _accept(websocket)
    _active_connections.setdefault(feature_id, []).append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await _send_json(websocket, {"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.get(feature_id, []).remove(websocket)
        if not _active_connections.get(feature_id):
            _active_connections.pop(feature_id, None)


async def push_feature_event(feature_id: str, event: dict[str, Any]) -> None:
    """Utility for services to push an event to all connections for a Feature."""
    event["timestamp"] = datetime.utcnow().isoformat()
    for ws in _active_connections.get(feature_id, []):
        try:
            await _send_json(ws, event)
        except Exception:
            pass
```

**Commit:**

```bash
git add backend/app/routers/__init__.py \
         backend/app/routers/projects.py \
         backend/app/routers/features.py \
         backend/app/routers/approvals.py \
         backend/app/routers/agents.py \
         backend/app/routers/websocket.py
git commit -m "feat: add all REST API routers with CRUD operations

添加 projects.py（Project CRUD）、features.py（Feature CRUD + 状态机占位）、approvals.py
（人工介入操作占位）、agents.py（AgentConfig CRUD）、websocket.py（WebSocket 连接管理），
状态机操作均返回 501，业务逻辑在后续迭代中实现
"
```

---

## Task 6: FastAPI 主入口

**Files**
- 创建: `backend/app/main.py`

### 步骤 6.1 创建 `backend/app/main.py`

```python
"""FastAPI application entry point.

Registers all routers, WebSocket endpoints, and startup/shutdown events.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import (
    agents_router,
    approvals_router,
    features_router,
    projects_router,
    websocket_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create all DB tables via managed schema.

    For production use, run `alembic upgrade head` via the Docker entrypoint
    instead of auto-creating tables here. This is a convenience for local dev.
    """
    from app.database import Base
    from app.models import (
        AgentConfig,
        Feature,
        FeatureExecution,
        Project,
        ReviewReport,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="solo100 API",
    description="AI-powered Feature development workflow engine.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Next.js dev server and production domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST routers
app.include_router(projects_router)
app.include_router(features_router)
app.include_router(approvals_router)
app.include_router(agents_router)

# Register WebSocket router
app.include_router(websocket_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root redirect to API docs."""
    return {"message": "solo100 API is running. See /docs for Swagger UI."}
```

**Commit:**

```bash
git add backend/app/main.py
git commit -m "feat: add FastAPI main entry point with all routers registered

添加 app/main.py：FastAPI 实例初始化、CORS 中间件、所有路由注册、health check 端点、
lifespan 事件（启动建表、关闭释放 engine）。前端可通过 /docs 访问 Swagger UI
"
```

---

## Task 7: 单元测试（TDD）

**Files**
- 创建: `backend/tests/__init__.py`
- 创建: `backend/tests/conftest.py`
- 创建: `backend/tests/unit/test_models.py`
- 创建: `backend/tests/unit/test_schemas.py`
- 创建: `backend/tests/unit/test_routers.py`

### 步骤 7.1 创建 `backend/tests/__init__.py`

```python
"""Test package for solo100 backend."""
```

### 步骤 7.2 创建 `backend/tests/conftest.py`

```python
"""Pytest configuration and shared fixtures for all unit/integration tests."""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

# Use an in-memory SQLite database for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

_TestSessionLocal = async_sessionmaker(
    bind=_test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db() -> AsyncGenerator[None, None]:
    """Create all tables before each test and drop them after."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh AsyncSession for each test."""
    async with _TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an AsyncClient that uses the test database session."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
```

### 步骤 7.3 创建 `backend/tests/unit/test_models.py`

```python
"""Unit tests for SQLAlchemy ORM models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentConfig, Feature, FeatureExecution, Project, ReviewReport
from app.models.feature import FeatureStatus
from app.models.feature_execution import ExecutionStage, ExecutionStatus


@pytest.mark.asyncio
async def test_project_create(db_session: AsyncSession) -> None:
    """Test creating a Project and persisting it."""
    project = Project(
        name="Test Project",
        ssh_url="git@github.com:test/repo.git",
        default_branch="main",
        ssh_key_env="SSH_KEY_TEST",
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)

    assert project.id is not None
    assert len(project.id) == 36
    assert project.name == "Test Project"
    assert project.default_agent_id is None
    assert project.created_at is not None


@pytest.mark.asyncio
async def test_project_default_branch(db_session: AsyncSession) -> None:
    """Test that default_branch defaults to 'main'."""
    project = Project(
        name="Demo",
        ssh_url="git@github.com:demo/repo.git",
        ssh_key_env="SSH_KEY",
    )
    db_session.add(project)
    await db_session.flush()
    assert project.default_branch == "main"


@pytest.mark.asyncio
async def test_feature_creation(db_session: AsyncSession) -> None:
    """Test creating a Feature under a Project."""
    project = Project(
        name="Proj",
        ssh_url="git@github.com:proj/repo.git",
        ssh_key_env="SSH_KEY",
    )
    db_session.add(project)
    await db_session.flush()

    feature = Feature(
        project_id=project.id,
        title="Add dark mode",
        description="Add a dark mode toggle to the UI.",
    )
    db_session.add(feature)
    await db_session.flush()

    assert feature.id is not None
    assert feature.status == FeatureStatus.PENDING.value
    assert feature.retry_count == 0
    assert feature.max_retries == 3
    assert feature.branch is None


@pytest.mark.asyncio
async def test_feature_execution(db_session: AsyncSession) -> None:
    """Test creating a FeatureExecution record."""
    project = Project(name="Proj", ssh_url="git@github.com:proj/repo.git", ssh_key_env="SSH_KEY")
    db_session.add(project)
    await db_session.flush()

    feature = Feature(project_id=project.id, title="Test Feature", description="Test desc")
    db_session.add(feature)
    await db_session.flush()

    execution = FeatureExecution(
        feature_id=feature.id,
        attempt_number=1,
        stage=ExecutionStage.BRAINSTORMING.value,
        status=ExecutionStatus.RUNNING.value,
    )
    db_session.add(execution)
    await db_session.flush()

    assert execution.id is not None
    assert execution.finished_at is None


@pytest.mark.asyncio
async def test_review_report(db_session: AsyncSession) -> None:
    """Test creating a ReviewReport."""
    project = Project(name="Proj", ssh_url="git@github.com:proj/repo.git", ssh_key_env="SSH_KEY")
    db_session.add(project)
    await db_session.flush()

    feature = Feature(project_id=project.id, title="Feature", description="Desc")
    db_session.add(feature)
    await db_session.flush()

    report = ReviewReport(
        feature_id=feature.id,
        attempt_number=1,
        ai_summary="Looks good overall.",
        ai_issues_json='[{"line": 10, "issue": "unused import"}]',
    )
    db_session.add(report)
    await db_session.flush()

    assert report.human_decision is None
    assert report.decided_at is None


@pytest.mark.asyncio
async def test_agent_config(db_session: AsyncSession) -> None:
    """Test creating an AgentConfig."""
    agent = AgentConfig(
        name="Claude Code Default",
        type="claude_code",
        api_key_env="ANTHROPIC_API_KEY",
        is_default=1,
    )
    db_session.add(agent)
    await db_session.flush()

    assert agent.is_default == 1
    assert agent.created_at is not None
    assert agent.updated_at is not None


@pytest.mark.asyncio
async def test_project_cascade_delete(db_session: AsyncSession) -> None:
    """Deleting a Project should cascade-delete its Features."""
    project = Project(
        name="Cascade Test",
        ssh_url="git@github.com:cascade/repo.git",
        ssh_key_env="SSH_KEY",
    )
    db_session.add(project)
    await db_session.flush()

    feature = Feature(
        project_id=project.id,
        title="Feature to Delete",
        description="Will be cascade-deleted.",
    )
    db_session.add(feature)
    await db_session.flush()
    feature_id = feature.id

    await db_session.delete(project)
    await db_session.flush()

    result = await db_session.get(Feature, feature_id)
    assert result is None
```

### 步骤 7.4 创建 `backend/tests/unit/test_schemas.py`

```python
"""Unit tests for Pydantic schemas."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentConfigCreate, AgentConfigUpdate
from app.schemas.feature import FeatureCreate, FeatureExecutionResponse, FeatureUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate


def test_project_create_schema_valid() -> None:
    """Valid ProjectCreate data should pass validation."""
    payload = ProjectCreate(
        name="My Project",
        ssh_url="git@github.com:me/repo.git",
        ssh_key_env="SSH_KEY_1",
    )
    assert payload.name == "My Project"
    assert payload.default_branch == "main"


def test_project_create_schema_rejects_empty_name() -> None:
    """Empty name should raise a ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ProjectCreate(name="", ssh_url="git@example.com", ssh_key_env="KEY")
    assert "name" in str(exc_info.value)


def test_project_update_partial() -> None:
    """Partial update (only name) should be valid."""
    payload = ProjectUpdate(name="New Name")
    assert payload.name == "New Name"
    assert payload.ssh_url is None
    assert payload.default_branch is None


def test_feature_create_schema() -> None:
    """FeatureCreate should require title and description."""
    payload = FeatureCreate(
        title="Add login",
        description="Implement OAuth2 login flow.",
    )
    assert payload.title == "Add login"
    assert payload.description.startswith("Implement")


def test_feature_create_rejects_empty_title() -> None:
    """Empty title should raise ValidationError."""
    with pytest.raises(ValidationError):
        FeatureCreate(title="", description="Some description")


def test_feature_update_partial() -> None:
    """Partial FeatureUpdate should only update provided fields."""
    payload = FeatureUpdate(title="Updated title")
    data = payload.model_dump(exclude_unset=True)
    assert data == {"title": "Updated title"}


def test_agent_config_create_defaults() -> None:
    """AgentConfigCreate should have sensible defaults."""
    payload = AgentConfigCreate(
        name="Claude Code",
        api_key_env="ANTHROPIC_API_KEY",
    )
    assert payload.type == "claude_code"
    assert payload.is_default is False


def test_agent_config_update_is_default() -> None:
    """AgentConfigUpdate should accept is_default toggle."""
    payload = AgentConfigUpdate(is_default=True)
    assert payload.is_default is True


def test_feature_execution_response_from_dict() -> None:
    """FeatureExecutionResponse should deserialize from ORM-like dict."""
    data = {
        "id": "abc-123",
        "feature_id": "feat-456",
        "attempt_number": 2,
        "stage": "planning",
        "status": "completed",
        "result_json": '{"tasks": []}',
        "started_at": datetime.utcnow(),
        "finished_at": datetime.utcnow(),
    }
    resp = FeatureExecutionResponse.model_validate(data)
    assert resp.attempt_number == 2
    assert resp.stage == "planning"
```

### 步骤 7.5 创建 `backend/tests/unit/test_routers.py`

```python
"""Integration-style unit tests for FastAPI routers.

These tests use the test database session fixture and the AsyncClient
to exercise each endpoint in isolation.
"""

import pytest
from httpx import AsyncClient


# =============================================================================
# Projects
# =============================================================================


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """POST /api/v1/projects should create and return a project."""
    response = await client.post(
        "/api/v1/projects",
        json={
            "name": "Backend Core",
            "ssh_url": "git@github.com:solo100/core.git",
            "ssh_key_env": "SSH_KEY_CORE",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Backend Core"
    assert data["default_branch"] == "main"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_and_get_project(client: AsyncClient) -> None:
    """Create a project then GET it by id."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Get Test",
            "ssh_url": "git@github.com:solo100/test.git",
            "ssh_key_env": "SSH_KEY_TEST",
        },
    )
    project_id = create_resp.json()["id"]

    get_resp = await client.get(f"/api/v1/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Get Test"


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient) -> None:
    """GET /api/v1/projects should return all projects."""
    for i in range(3):
        await client.post(
            "/api/v1/projects",
            json={
                "name": f"Project {i}",
                "ssh_url": f"git@github.com:solo100/p{i}.git",
                "ssh_key_env": f"SSH_KEY_P{i}",
            },
        )
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """PUT /api/v1/projects/{id} should update fields."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Old Name",
            "ssh_url": "git@github.com:solo100/old.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "New Name"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """DELETE /api/v1/projects/{id} should remove the project."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "To Delete",
            "ssh_url": "git@github.com:solo100/delete.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/projects/{project_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_get_nonexistent_project_returns_404(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id} should return 404 for unknown id."""
    resp = await client.get("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404


# =============================================================================
# Features
# =============================================================================


@pytest.mark.asyncio
async def test_create_feature(client: AsyncClient) -> None:
    """POST /api/v1/projects/{id}/features should create a Feature."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Feature Test Project",
            "ssh_url": "git@github.com:solo100/feat.git",
            "ssh_key_env": "SSH_KEY_FEAT",
        },
    )
    project_id = proj_resp.json()["id"]

    resp = await client.post(
        f"/api/v1/projects/{project_id}/features",
        json={
            "title": "Add user profile",
            "description": "Allow users to edit their profile.",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Add user profile"
    assert data["status"] == "pending"
    assert data["retry_count"] == 0


@pytest.mark.asyncio
async def test_create_feature_404_on_unknown_project(client: AsyncClient) -> None:
    """POST /api/v1/projects/{id}/features should 404 if project does not exist."""
    resp = await client.post(
        "/api/v1/projects/nonexistent/features",
        json={"title": "X", "description": "Y"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_features_by_project(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id}/features should list features for that project."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "List Test",
            "ssh_url": "git@github.com:solo100/list.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = proj_resp.json()["id"]

    for title in ["Feature A", "Feature B"]:
        await client.post(
            f"/api/v1/projects/{project_id}/features",
            json={"title": title, "description": "Desc"},
        )

    resp = await client.get(f"/api/v1/projects/{project_id}/features")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_get_feature_executions(client: AsyncClient) -> None:
    """GET /api/v1/features/{id}/executions should return execution records."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Exec Test",
            "ssh_url": "git@github.com:solo100/exec.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = proj_resp.json()["id"]

    feat_resp = await client.post(
        f"/api/v1/projects/{project_id}/features",
        json={"title": "Execution Test", "description": "Desc"},
    )
    feature_id = feat_resp.json()["id"]

    resp = await client.get(f"/api/v1/features/{feature_id}/executions")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_get_feature_review_returns_none_when_empty(client: AsyncClient) -> None:
    """GET /api/v1/features/{id}/review should return null if no report exists."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Review Test",
            "ssh_url": "git@github.com:solo100/review.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = proj_resp.json()["id"]

    feat_resp = await client.post(
        f"/api/v1/projects/{project_id}/features",
        json={"title": "Review Feature", "description": "Desc"},
    )
    feature_id = feat_resp.json()["id"]

    resp = await client.get(f"/api/v1/features/{feature_id}/review")
    assert resp.status_code == 200
    assert resp.json() is None


# =============================================================================
# State-machine operations (501 placeholders)
# =============================================================================


@pytest.mark.asyncio
async def test_start_feature_returns_501(client: AsyncClient) -> None:
    """POST /api/v1/features/{id}/start should return 501 until implemented."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Start Test",
            "ssh_url": "git@github.com:solo100/start.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = proj_resp.json()["id"]
    feat_resp = await client.post(
        f"/api/v1/projects/{project_id}/features",
        json={"title": "Start Feature", "description": "Desc"},
    )
    feature_id = feat_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/start")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_approve_returns_501(client: AsyncClient) -> None:
    """POST /api/v1/features/{id}/approve should return 501 until implemented."""
    proj_resp = await client.post(
        "/api/v1/projects",
        json={
            "name": "Approve Test",
            "ssh_url": "git@github.com:solo100/approve.git",
            "ssh_key_env": "SSH_KEY",
        },
    )
    project_id = proj_resp.json()["id"]
    feat_resp = await client.post(
        f"/api/v1/projects/{project_id}/features",
        json={"title": "Approve Feature", "description": "Desc"},
    )
    feature_id = feat_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/approve")
    assert resp.status_code == 501


# =============================================================================
# Agents
# =============================================================================


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient) -> None:
    """POST /api/v1/agents should create an agent config."""
    resp = await client.post(
        "/api/v1/agents",
        json={
            "name": "Claude Code Primary",
            "type": "claude_code",
            "api_key_env": "ANTHROPIC_API_KEY",
            "is_default": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Claude Code Primary"
    assert data["is_default"] is True


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient) -> None:
    """GET /api/v1/agents should return all agent configs."""
    for name in ["Agent A", "Agent B"]:
        await client.post(
            "/api/v1/agents",
            json={"name": name, "api_key_env": "ANTHROPIC_API_KEY"},
        )
    resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient) -> None:
    """PUT /api/v1/agents/{id} should update the agent config."""
    create_resp = await client.post(
        "/api/v1/agents",
        json={"name": "Old Agent", "api_key_env": "ANTHROPIC_API_KEY"},
    )
    agent_id = create_resp.json()["id"]

    update_resp = await client.put(
        f"/api/v1/agents/{agent_id}",
        json={"name": "New Agent"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "New Agent"


@pytest.mark.asyncio
async def test_update_nonexistent_agent_returns_404(client: AsyncClient) -> None:
    """PUT /api/v1/agents/{id} should return 404 for unknown id."""
    resp = await client.put(
        "/api/v1/agents/nonexistent",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# =============================================================================
# Health
# =============================================================================


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """GET /health should return ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
```

**Commit:**

```bash
git add backend/tests/__init__.py \
         backend/tests/conftest.py \
         backend/tests/unit/test_models.py \
         backend/tests/unit/test_schemas.py \
         backend/tests/unit/test_routers.py
git commit -m "test: add unit and integration tests for models, schemas and routers

添加 conftest.py（AsyncSession + AsyncClient fixtures，in-memory SQLite）、
test_models.py（所有 5 个模型的 CRUD 测试，含 cascade delete）、
test_schemas.py（Pydantic 验证测试）、
test_routers.py（所有 REST 端点测试，含 501 占位验证），
遵循 TDD 先测试后实现原则
"
```

---

## Task 8: 最终验证

### 步骤 8.1 语法检查

```bash
cd /home/codingdie/codes/solo100/backend && \
  python -m py_compile app/config.py app/database.py \
    app/models/project.py app/models/feature.py \
    app/models/feature_execution.py app/models/review_report.py \
    app/models/agent_config.py \
    app/schemas/project.py app/schemas/feature.py app/schemas/agent.py \
    app/routers/projects.py app/routers/features.py \
    app/routers/approvals.py app/routers/agents.py \
    app/routers/websocket.py \
    app/main.py && echo "All files compile OK"
```

### 步骤 8.2 运行单元测试

```bash
cd /home/codingdie/codes/solo100/backend && \
  pip install -q pytest pytest-asyncio aiosqlite httpx && \
  PYTHONPATH=. pytest tests/ -v --tb=short 2>&1 | tail -40
```

预期输出：所有测试 PASSED，无 skipped/failed。

### 步骤 8.3 启动服务器验证

```bash
cd /home/codingdie/codes/solo100/backend && \
  pip install -q fastapi uvicorn sqlalchemy aiosqlite && \
  timeout 5 uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 || true
```

验证日志中无 ImportError 或 ModuleNotFoundError。

### 步骤 8.4 提交最终 Commit

```bash
git add -A
git status
# 确认只有 backend/ 下的文件变更
git commit -m "chore: verify backend foundation — all tests pass and server starts

Task 8 验证步骤：语法编译通过、pytest 全部通过、uvicorn 启动无错误
"
```

---

## 顺序依赖关系

```
Task 1  (脚手架)
    └─→ Task 2  (config + database + alembic)
              └─→ Task 3  (ORM 模型，依赖 database.py)
                        └─→ Task 4  (Pydantic schemas)
                                  └─→ Task 5  (API 路由，依赖 models + schemas)
                                            └─→ Task 6  (main.py，依赖 routers)
                                                      └─→ Task 7  (tests，依赖所有)
                                                                └─→ Task 8  (验证)
```

---

## 风险与注意事项

1. **Alembic migration vs auto-create**: `lifespan` 中使用 `Base.metadata.create_all` 仅用于本地开发。生产部署应改用 `alembic upgrade head`。建议在 Docker entrypoint 中优先调用 Alembic 迁移。
2. **is_default 字段类型**: SQLite 中 `INTEGER` 类型，`server_default="0"` 会存为整数 0，ORM 映射到 Python `int`。PUT 时注意 Pydantic schema 中 `is_default: bool | None`，转换在 router 层处理。
3. **WebSocket 连接内存存储**: 当前 `_active_connections` 是进程内字典，不适用于多 worker 部署（gunicorn/uvicorn --workers > 1）。后续接入 Redis pub/sub 后可移除此内存存储。
4. **异步 Session 并发**: `pytest-asyncio` 的默认事件循环策略需与 DB 事务隔离级别匹配。测试 fixture 使用 `autouse=True` 确保每个测试独立建表。
5. **飞书 Webhook URL**: v0.1 仅从环境变量读取，不持久化到数据库。如后续需要多项目独立飞书配置，可扩展 `project` 表添加 `feishu_webhook_url` 字段。
