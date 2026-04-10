"""Integration test fixtures — real DB, real Redis, real Git."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from httpx import Client
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 统一使用环境变量配置测试路径
TEST_DB = os.getenv("TEST_DATABASE_PATH", "/tmp/solo100-integration.db")
TEST_GIT_REMOTE = os.getenv("TEST_GIT_REMOTE", "/tmp/solo100-test-remote.git")
TEST_WORKTREE_ROOT = os.getenv("TEST_WORKTREE_ROOT", "/tmp/solo100-test-worktrees")


@pytest.fixture(scope="session", autouse=True)
def setup_git_remote():
    """创建临时 bare Git repo 作为测试用的远程仓库。"""
    Path(TEST_GIT_REMOTE).mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "--bare", "."],
        cwd=TEST_GIT_REMOTE,
        check=True,
        capture_output=True,
    )
    yield
    # teardown: 保留供后续调试，CI 环境下容器退出自动清理


@pytest.fixture(scope="session")
def git_worktree_root():
    """每个测试 session 分配一个临时目录用于 worktree。"""
    Path(TEST_WORKTREE_ROOT).mkdir(parents=True, exist_ok=True)
    yield TEST_WORKTREE_ROOT
    # teardown
    import shutil
    shutil.rmtree(TEST_WORKTREE_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def db_engine():
    """使用真实 SQLite 文件数据库。"""
    # 先清理旧文件
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    engine = create_engine(f"sqlite:///{TEST_DB}", echo=False)
    from app.database import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """每个测试函数分配一个独立的数据库 session，使用事务回滚保证隔离。"""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()  # 回滚所有修改，保证测试隔离
        connection.close()


@pytest.fixture(scope="session")
def sync_client(db_engine):
    """同步 HTTP client，base_url 指向真实运行的 backend。"""
    import time

    # 等待 backend 就绪（最多 30 秒）
    backend_ready = False
    for i in range(30):
        try:
            resp = Client(base_url="http://localhost:8000", timeout=2.0).get("/health")
            if resp.status_code == 200:
                backend_ready = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not backend_ready:
        raise RuntimeError("Backend not ready after 30 seconds")

    client = Client(base_url="http://localhost:8000", timeout=30.0)
    yield client
    client.close()


@pytest.fixture
def mock_agent():
    """注入 MockClaudeCodeAgent。集成测试不使用真实 Agent。"""
    from tests.integration.mock_agent import MockClaudeCodeAgent
    return MockClaudeCodeAgent()
