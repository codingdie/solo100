# solo100 集成测试实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一套完整的端到端集成测试体系，通过单一 Docker 镜像一键运行后端 pytest 集成测试 + 前端 Playwright E2E 测试。

**Architecture:** 单一测试镜像 `solo100-test`，内置 backend + redis + frontend 服务，集成测试走真实 HTTP（AsyncClient → localhost:8000），Mock Agent 固定返回结构化数据，不调用真实 LLM API。

**Tech Stack:** pytest, pytest-asyncio, httpx (sync client), Playwright, FastAPI, uvicorn, SQLite, Redis, GitPython

---

## 文件概览

| 操作 | 文件 |
|---|---|
| Create | `Dockerfile.test` |
| Create | `entrypoint-test.sh` |
| Create | `backend/tests/integration/conftest.py` |
| Create | `backend/tests/integration/mock_agent.py` |
| Create | `backend/tests/integration/test_projects.py` |
| Create | `backend/tests/integration/test_features.py` |
| Create | `backend/tests/integration/test_feature_workflow.py` |
| Create | `frontend/tests/e2e/playwright.config.ts` |
| Create | `frontend/tests/e2e/conftest.ts` |
| Create | `frontend/tests/e2e/projects.spec.ts` |
| Create | `frontend/tests/e2e/feature-workflow.spec.ts` |
| Modify | `backend/requirements.txt` (新增 playwright) |
| Modify | `frontend/package.json` (新增 @playwright/test) |

---

## Task 1: MockClaudeCodeAgent 实现

**Files:**
- Create: `backend/tests/integration/mock_agent.py`
- Test: 运行 `pytest backend/tests/unit/test_base_agent.py -v` 确认现有单元测试不被破坏

- [ ] **Step 1: 编写 mock_agent.py**

实现 `MockClaudeCodeAgent`，继承 `BaseAgent`，固定返回结构化数据：

```python
"""Mock implementation of BaseAgent for integration tests."""

from app.agents.base import BaseAgent
from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


class MockClaudeCodeAgent(BaseAgent):
    """Returns fixed structured results without calling any LLM API."""

    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log=None,
    ) -> BrainstormResult:
        if failure_reason:
            return BrainstormResult(
                analysis=f"Mock re-analysis after failure: {failure_reason}",
                acceptance_criteria=["验收条件1", "验收条件2"],
                key_points=["关键点1", "关键点2"],
                estimated_risk="low",
            )
        return BrainstormResult(
            analysis="Mock: 分析需求完成",
            acceptance_criteria=["验收条件1", "验收条件2"],
            key_points=["关键点1", "关键点2"],
            estimated_risk="low",
        )

    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log=None,
    ) -> Plan:
        if previous_plan:
            return Plan(
                tasks=[
                    {"title": "修订任务1", "description": "在已有基础上修改", "files": ["a.py"]},
                ],
                estimated_risk="low",
                raw_output="Mock revised plan",
            )
        return Plan(
            tasks=[
                {
                    "title": "任务1：实现基础结构",
                    "description": "创建 a.py 并实现基础结构",
                    "files": ["a.py"],
                },
                {
                    "title": "任务2：实现核心逻辑",
                    "description": "创建 b.py 并实现核心逻辑",
                    "files": ["b.py"],
                },
            ],
            estimated_risk="low",
            raw_output="Mock plan output",
        )

    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log=None,
    ) -> ImplementResult:
        import os
        for task in plan.tasks:
            for file_path in task.get("files", []):
                full_path = os.path.join(worktree_path, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(f"# Mock implementation for {file_path}\n")
        return ImplementResult(
            files_changed=[f for t in plan.tasks for f in t.get("files", [])],
            summary="Mock: 代码实现完成",
            commit_hash="abc1234",
        )
```

- [ ] **Step 2: 验证 mock_agent 满足 BaseAgent 接口**

Run: `PYTHONPATH=backend python3 -c "from tests.integration.mock_agent import MockClaudeCodeAgent; from app.agents.base import BaseAgent; assert issubclass(MockClaudeCodeAgent, BaseAgent); print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/mock_agent.py
git commit -m "test: add MockClaudeCodeAgent for integration tests"
```

---

## Task 2: 后端集成测试 conftest.py

**Files:**
- Create: `backend/tests/integration/conftest.py`
- Modify: `backend/tests/conftest.py` (追加 integration 路径说明)

- [ ] **Step 1: 创建 `backend/tests/integration/conftest.py`**

```python
"""Integration test fixtures — real DB, real Redis, real Git."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest
from httpx import Client
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

TEST_DB = "/tmp/solo100-integration.db"
TEST_GIT_REMOTE = "/tmp/solo100-test-remote.git"
TEST_WORKTREE_ROOT = "/tmp/solo100-test-worktrees"


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
    """每个测试函数分配一个独立的数据库 session。"""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(scope="session")
def sync_client(db_engine):
    """同步 HTTP client，base_url 指向真实运行的 backend。"""
    # 等待外部启动 backend（由 entrypoint-test.sh 管理）
    # 此 fixture 假设 backend 已在 localhost:8000 运行
    client = Client(base_url="http://localhost:8000", timeout=30.0)
    yield client
    client.close()


@pytest.fixture
def mock_agent():
    """注入 MockClaudeCodeAgent。集成测试不使用真实 Agent。"""
    from tests.integration.mock_agent import MockClaudeCodeAgent
    return MockClaudeCodeAgent()
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/integration/conftest.py
git commit -m "test: add integration conftest with real DB and Git fixtures"
```

---

## Task 3: 后端集成测试 — Projects API

**Files:**
- Create: `backend/tests/integration/test_projects.py`

- [ ] **Step 1: 编写 `test_projects.py`**

```python
"""Integration tests for Projects API — real HTTP + real DB."""

import pytest


class TestProjectsAPI:
    """测试 /api/projects 端点。"""

    def test_create_project(self, sync_client, db_session):
        """POST /api/projects 返回 201 且包含 id 和 name。"""
        payload = {
            "name": "test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        }
        response = sync_client.post("/api/projects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-project"
        assert data["ssh_url"] == payload["ssh_url"]

    def test_list_projects(self, sync_client, db_session):
        """GET /api/projects 返回项目列表。"""
        # 先创建一个项目
        sync_client.post("/api/projects", json={
            "name": "list-test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        response = sync_client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(p["name"] == "list-test-project" for p in data)

    def test_get_project(self, sync_client, db_session):
        """GET /api/projects/{id} 返回单个项目详情。"""
        create_resp = sync_client.post("/api/projects", json={
            "name": "get-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["id"] == project_id

    def test_delete_project(self, sync_client, db_session):
        """DELETE /api/projects/{id} 返回 204。"""
        create_resp = sync_client.post("/api/projects", json={
            "name": "delete-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 204
        # 再次获取应返回 404
        assert sync_client.get(f"/api/projects/{project_id}").status_code == 404
```

- [ ] **Step 2: 验证测试文件语法**

Run: `PYTHONPATH=backend python3 -m py_compile backend/tests/integration/test_projects.py`

Expected: 无输出（成功）

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_projects.py
git commit -m "test: add Projects API integration tests"
```

---

## Task 4: 后端集成测试 — Features API

**Files:**
- Create: `backend/tests/integration/test_features.py`

- [ ] **Step 1: 编写 `test_features.py`**

```python
"""Integration tests for Features API — real HTTP + real DB."""

import pytest


def _create_project(client):
    """Helper: 创建测试用项目，返回 project_id。"""
    resp = client.post("/api/projects", json={
        "name": "feature-test-project",
        "ssh_url": "file:///tmp/solo100-test-remote.git",
        "default_branch": "main",
        "ssh_key_env": "TEST_SSH_KEY",
    })
    return resp.json()["id"]


class TestFeaturesAPI:
    """测试 /api/features 端点。"""

    def test_create_feature(self, sync_client, db_session):
        """POST /api/features 返回 201，状态为 pending。"""
        project_id = _create_project(sync_client)
        payload = {
            "project_id": project_id,
            "title": "测试 Feature",
            "description": "这是一个集成测试 Feature",
        }
        response = sync_client.post("/api/features", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["title"] == "测试 Feature"
        assert data["project_id"] == project_id

    def test_list_features_by_project(self, sync_client, db_session):
        """GET /api/features?project_id=xxx 返回该项目的所有 Feature。"""
        project_id = _create_project(sync_client)
        # 创建两个 feature
        for i in range(2):
            sync_client.post("/api/features", json={
                "project_id": project_id,
                "title": f"Feature {i}",
                "description": f"描述 {i}",
            })
        response = sync_client.get(f"/api/features?project_id={project_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_feature(self, sync_client, db_session):
        """GET /api/features/{id} 返回 Feature 详情。"""
        project_id = _create_project(sync_client)
        create_resp = sync_client.post("/api/features", json={
            "project_id": project_id,
            "title": "get-feature-test",
            "description": "测试 GET",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/features/{feature_id}")
        assert response.status_code == 200
        assert response.json()["id"] == feature_id

    def test_update_feature_status(self, sync_client, db_session):
        """PATCH /api/features/{id} 可更新 status 等字段。"""
        project_id = _create_project(sync_client)
        create_resp = sync_client.post("/api/features", json={
            "project_id": project_id,
            "title": "patch-test",
            "description": "测试 PATCH",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.patch(
            f"/api/features/{feature_id}",
            json={"status": "archived"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "archived"
```

- [ ] **Step 2: Commit**

```bash
git add backend/tests/integration/test_features.py
git commit -m "test: add Features API integration tests"
```

---

## Task 5: 后端集成测试 — 完整状态机流程

**Files:**
- Create: `backend/tests/integration/test_feature_workflow.py`

**注意:** `FeatureExecutor.run_pipeline()` 内部有 `wait_for_approval()` 阻塞等待（最多 MAX_WAIT_CYCLES * POLL_INTERVAL 秒），集成测试不能直接调用。测试策略是：通过 API 触发 stage 切换，验证每个状态流转正确。

- [ ] **Step 1: 编写 `test_feature_workflow.py`**

```python
"""Integration tests for complete Feature state machine workflow."""

import pytest


def _create_project(client):
    resp = client.post("/api/projects", json={
        "name": "workflow-test-project",
        "ssh_url": "file:///tmp/solo100-test-remote.git",
        "default_branch": "main",
        "ssh_key_env": "TEST_SSH_KEY",
    })
    return resp.json()["id"]


def _create_feature(client, project_id, title="workflow-feature"):
    resp = client.post("/api/features", json={
        "project_id": project_id,
        "title": title,
        "description": "测试完整流程的 Feature",
    })
    return resp.json()["id"], resp.json()


class TestFeatureWorkflow:
    """测试完整状态机：pending → merged。"""

    def test_workflow_full_happy_path(self, sync_client, db_session):
        """完整流程：pending → brainstorming → planning → implementing → testing → reviewing → approved → verifying → merged。"""
        project_id = _create_project(sync_client)
        feature_id, feature = _create_feature(sync_client, project_id)
        assert feature["status"] == "pending"

        # 启动 pipeline（内部会进入 brainstorming 状态并等待 approval）
        resp = sync_client.post(f"/api/features/{feature_id}/start")
        assert resp.status_code in (200, 202)
        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "brainstorming"

        # 人工介入点 1: 确认 brainstorming
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "brainstorming",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "planning"

        # 人工介入点 2: 确认 plan
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "planning",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "implementing"

        # implementing 完成后进入 testing（需要等待 Celery 任务，这里通过 API 推进）
        # 模拟 implementing 结束：更新状态 + 填充必要数据
        resp = sync_client.patch(f"/api/features/{feature_id}", json={
            "status": "testing",
        })
        assert resp.status_code == 200

        # 人工介入点 3: 确认 test 结果
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "testing",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "reviewing"

        # 人工介入点 4: code review approve
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "reviewing",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "approved"

        # 人工最终确认 → verifying → merged
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "approved",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        final_status = resp.json()["status"]
        # verifying 可能因为 Git merge conflict 等原因失败，这里只验证状态进入了 verifying 或 merged
        assert final_status in ("verifying", "merged"), f"Expected verifying or merged, got {final_status}"

    def test_workflow_reject_at_brainstorming(self, sync_client, db_session):
        """brainstorming 阶段 reject 后人工选择 retry 的流程。"""
        project_id = _create_project(sync_client)
        feature_id, _ = _create_feature(sync_client, project_id, "reject-test")

        # 启动
        sync_client.post(f"/api/features/{feature_id}/start")
        assert sync_client.get(f"/api/features/{feature_id}").json()["status"] == "brainstorming"

        # reject
        resp = sync_client.post(f"/api/approvals/{feature_id}/reject", json={
            "stage": "brainstorming",
            "failure_reason": "分析不够深入",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "pending"

    def test_workflow_approved_state_blocks_start(self, sync_client, db_session):
        """已经在 approved 状态的 Feature 不能再次 start。"""
        project_id = _create_project(sync_client)
        feature_id, _ = _create_feature(sync_client, project_id)

        # 手动设置到 approved
        sync_client.patch(f"/api/features/{feature_id}", json={"status": "approved"})

        resp = sync_client.post(f"/api/features/{feature_id}/start")
        # 应该拒绝或返回错误
        assert resp.status_code in (400, 409)
```

- [ ] **Step 2: 验证语法**

Run: `PYTHONPATH=backend python3 -m py_compile backend/tests/integration/test_feature_workflow.py`

Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_feature_workflow.py
git commit -m "test: add Feature workflow integration tests"
```

---

## Task 6: 前端 Playwright 配置

**Files:**
- Create: `frontend/tests/e2e/playwright.config.ts`
- Create: `frontend/tests/e2e/conftest.ts`
- Modify: `frontend/package.json` (新增 @playwright/test 依赖)

- [ ] **Step 1: 添加 `@playwright/test` 依赖到 `frontend/package.json`**

检查现有 `package.json`，在 `devDependencies` 中追加：

```json
"@playwright/test": "^1.42.0"
```

Run: `cd frontend && npm install @playwright/test@^1.42.0 --save-dev`

- [ ] **Step 2: 创建 `frontend/tests/e2e/playwright.config.ts`**

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // webServer 由 entrypoint-test.sh 管理，不在此配置
});
```

- [ ] **Step 3: 创建 `frontend/tests/e2e/conftest.ts`**

```typescript
import { test as base, Page } from '@playwright/test';

/** 自定义 test fixture，带默认 timeout。 */
export const test = base.extend<{ testPage: Page }>({
  testPage: async ({ page }, use) => {
    await use(page);
  },
});

export { expect } from '@playwright/test';
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/tests/e2e/playwright.config.ts frontend/tests/e2e/conftest.ts
git commit -m "test: add Playwright config and base fixtures for E2E tests"
```

---

## Task 7: 前端 E2E 测试 — Projects 页面

**Files:**
- Create: `frontend/tests/e2e/projects.spec.ts`

- [ ] **Step 1: 编写 `projects.spec.ts`**

```typescript
import { expect, test } from './conftest';

test.describe('Projects Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/projects');
  });

  test('should display projects list page', async ({ page }) => {
    await expect(page).toHaveTitle(/solo100/i);
    // 检查页面加载了 projects 相关内容（标题或空状态）
    const heading = page.getByRole('heading', { name: /project/i }).or(page.getByText('No projects'));
    await expect(heading).toBeVisible();
  });

  test('should create a new project', async ({ page }) => {
    // 导航到创建页面
    await page.getByRole('link', { name: /new project/i }).or(page.getByRole('button', { name: /new project/i })).click();

    // 填写表单
    await page.getByLabel(/name/i).fill('e2e-test-project');
    await page.getByLabel(/ssh url/i).fill('file:///tmp/solo100-test-remote.git');
    await page.getByLabel(/default branch/i).fill('main');

    // 提交
    await page.getByRole('button', { name: /create|submit|save/i }).click();

    // 验证项目出现在列表中
    await expect(page.getByText('e2e-test-project')).toBeVisible();
  });
});
```

- [ ] **Step 2: 验证文件语法**

Run: `cd frontend && npx tsc --noEmit tests/e2e/projects.spec.ts 2>&1 | head -20`

Expected: 无严重错误（允许 @playwright/test 类型未安装导致的 minor 错误）

- [ ] **Step 3: Commit**

```bash
git add frontend/tests/e2e/projects.spec.ts
git commit -m "test: add Projects E2E test with Playwright"
```

---

## Task 8: 前端 E2E 测试 — Feature Workflow 页面

**Files:**
- Create: `frontend/tests/e2e/feature-workflow.spec.ts`

- [ ] **Step 1: 编写 `feature-workflow.spec.ts`**

```typescript
import { expect, test } from './conftest';

/** 创建测试用项目并返回其 URL */
async function createTestProject(page: import('@playwright/test').Page, name = 'e2e-workflow-project') {
  await page.goto('/projects');
  await page.getByRole('button', { name: /new project/i }).click();
  await page.getByLabel(/name/i).fill(name);
  await page.getByLabel(/ssh url/i).fill('file:///tmp/solo100-test-remote.git');
  await page.getByLabel(/default branch/i).fill('main');
  await page.getByRole('button', { name: /create|submit|save/i }).click();
  await expect(page.getByText(name)).toBeVisible();
}

test.describe('Feature Workflow', () => {
  test('should create and start a feature', async ({ page }) => {
    await createTestProject(page);

    // 创建 Feature
    await page.getByRole('button', { name: /new feature/i }).click();
    await page.getByLabel(/title/i).fill('e2e-test-feature');
    await page.getByLabel(/description/i).fill('Playwright E2E 测试 Feature');
    await page.getByRole('button', { name: /create|submit|save/i }).click();
    await expect(page.getByText('e2e-test-feature')).toBeVisible();

    // 启动开发流程
    const featureCard = page.getByText('e2e-test-feature').locator('..');
    await featureCard.getByRole('button', { name: /start/i }).click();

    // 验证状态变为 brainstorming
    await expect(page.getByText(/brainstorming/i)).toBeVisible({ timeout: 5000 });
  });

  test('should show feature detail with status badge', async ({ page }) => {
    await createTestProject(page);
    await page.getByRole('button', { name: /new feature/i }).click();
    await page.getByLabel(/title/i).fill('detail-test-feature');
    await page.getByLabel(/description/i).fill('测试详情页');
    await page.getByRole('button', { name: /create|submit|save/i }).click();

    // 点击查看详情
    await page.getByText('detail-test-feature').click();
    await expect(page.getByText('pending')).toBeVisible();
    await expect(page.getByText('detail-test-feature')).toBeVisible();
  });
});
```

- [ ] **Step 2: Commit**

```bash
git add frontend/tests/e2e/feature-workflow.spec.ts
git commit -m "test: add Feature Workflow E2E test with Playwright"
```

---

## Task 9: Dockerfile.test 和 entrypoint-test.sh

**Files:**
- Create: `Dockerfile.test`（在项目根目录）
- Create: `entrypoint-test.sh`（在项目根目录）
- Modify: `backend/requirements.txt`（新增 playwright）

- [ ] **Step 1: 添加 playwright 到 `backend/requirements.txt`**

追加一行：
```
playwright==1.42.0
```

- [ ] **Step 2: 创建 `Dockerfile.test`**

```dockerfile
# ─────────────────────────────────────────────
# Stage 1: Python 依赖
# ─────────────────────────────────────────────
FROM python:3.11-slim AS python_deps

WORKDIR /deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir playwright==1.42.0

# ─────────────────────────────────────────────
# Stage 2: Node.js 依赖
# ─────────────────────────────────────────────
FROM node:20-slim AS node_deps

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --ignore-scripts || npm install --ignore-scripts

# ─────────────────────────────────────────────
# 最终镜像
# ─────────────────────────────────────────────
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl redis-server wait-for-it \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖层
COPY --from=python_deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python_deps /usr/local/bin /usr/local/bin

# 复制 Node.js 依赖层
COPY --from=node_deps /frontend/node_modules /frontend/node_modules

# 安装 Playwright 浏览器
RUN playwright install --with-deps chromium

# 复制源码
COPY backend/ /app
COPY frontend/ /frontend

# 非 root 用户
RUN useradd --create-home --shell /bin/bash testuser && \
    chown -R testuser:testuser /app /frontend
USER testuser

COPY --chmod=755 entrypoint-test.sh /entrypoint-test.sh

WORKDIR /app

CMD ["/entrypoint-test.sh"]
```

- [ ] **Step 3: 创建 `entrypoint-test.sh`**

```bash
#!/bin/bash
set -e

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo "Cleaning up..."
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

# 1. 初始化临时 Git bare repo
echo "=== Setting up test Git remote ==="
mkdir -p /tmp/solo100-test-remote.git
git init --bare /tmp/solo100-test-remote.git 2>/dev/null || true

# 2. 启动 Redis
echo "=== Starting Redis ==="
redis-server --daemonize yes --port 6379
wait-for-it localhost:6379 --timeout=10 -- echo "Redis ready"

# 3. 设置环境变量
export PYTHONPATH=/app
export DATABASE_URL=sqlite+aiosqlite:////tmp/solo100-integration.db
export REDIS_URL=redis://localhost:6379
export SECRET_KEY=test-secret-key-for-integration
export ANTHROPIC_API_KEY=test_key
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 4. 初始化数据库
echo "=== Setting up database ==="
cd /app
python3 -c "from app.database import engine, Base; import app.models; Base.metadata.create_all(engine); print('DB schema ready')"

# 5. 启动 backend
echo "=== Starting backend ==="
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
wait-for-it localhost:8000 --timeout=30 -- echo "Backend ready at http://localhost:8000"

# 6. 构建并启动 frontend
echo "=== Building frontend ==="
cd /frontend
npm run build
PORT=3000 npx next start -p 3000 &
FRONTEND_PID=$!
wait-for-it localhost:3000 --timeout=120 -- echo "Frontend ready at http://localhost:3000"

# 7. 运行后端集成测试
echo "=== Running backend integration tests ==="
cd /app
pytest tests/integration/ -v --tb=short --color=yes
BACKEND_RESULT=$?

# 8. 运行前端 E2E 测试
echo "=== Running frontend E2E tests ==="
cd /frontend
npx playwright test --reporter=list
PLAYWRIGHT_RESULT=$?

# 9. 汇总结果
echo ""
echo "========================================"
if [ $BACKEND_RESULT -eq 0 ] && [ $PLAYWRIGHT_RESULT -eq 0 ]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "TESTS FAILED (backend=$BACKEND_RESULT, playwright=$PLAYWRIGHT_RESULT)"
    exit 1
fi
```

- [ ] **Step 4: 验证脚本语法**

Run: `bash -n entrypoint-test.sh && echo "Syntax OK"`

Expected: `Syntax OK`

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.test entrypoint-test.sh backend/requirements.txt
git commit -m "test: add Dockerfile.test and entrypoint-test.sh for full E2E integration test suite"
```

---

## Task 10: 本地验证（在 Docker 外运行子集）

**Files:** 无文件变更

- [ ] **Step 1: 在宿主机安装依赖**

```bash
# 安装 Playwright
pip install playwright
playwright install --with-deps chromium

# 安装 Node 依赖
cd frontend && npm install @playwright/test@^1.42.0 --save-dev
```

- [ ] **Step 2: 启动 Redis**

```bash
redis-server --daemonize yes
```

- [ ] **Step 3: 启动 backend（在另一个终端）**

```bash
cd backend
export PYTHONPATH=/home/codingdie/codes/solo100/backend
export DATABASE_URL=sqlite+aiosqlite:////tmp/solo100-integration.db
export REDIS_URL=redis://localhost:6379
export SECRET_KEY=test-secret-key
export ANTHROPIC_API_KEY=test_key
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/0
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 4: 运行后端集成测试**

```bash
cd backend
PYTHONPATH=. pytest tests/integration/test_projects.py -v --tb=short
```

Expected: 全部 PASS

- [ ] **Step 5: 构建并启动 frontend**

```bash
cd frontend && npm run build && npx next start -p 3000 &
```

- [ ] **Step 6: 运行前端 E2E 测试**

```bash
cd frontend
npx playwright test tests/e2e/projects.spec.ts --reporter=list
```

Expected: 全部 PASS

---

## 自检清单

| 检查项 | 状态 |
|---|---|
| spec 第 1 节（目标）：后端集成测试 + 前端 E2E + 状态机流程 | Task 3/4/5 + 7/8 |
| spec 第 3 节（文件结构）：所有列出的文件均已计划 | ✓ |
| spec 第 4 节（entrypoint）：Git init + Redis + DB init + backend + frontend + pytest + playwright | Task 9 |
| spec 第 5 节（后端集成测试）：conftest + mock_agent + test_projects/features/workflow | Task 1/2/3/4/5 |
| spec 第 6 节（前端 E2E）：playwright.config + conftest + projects + feature-workflow | Task 6/7/8 |
| spec 第 8 节（Dockerfile.test）：所有层 + wait-for-it + 非 root | Task 9 |
| 无 placeholder（TBD/TODO/实现后续） | ✓ |
| 类型一致性：Plan.tasks 是 list[dict]，MockAgent 正确返回 dict | ✓ |
| Task 顺序：先 mock agent → conftest → API tests → frontend → docker | ✓ |
