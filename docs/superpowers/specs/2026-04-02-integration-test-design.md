# solo100 集成测试设计文档

**日期**: 2026-04-02
**状态**: 草稿

---

## 1. 目标

为 solo100 构建端到端集成测试体系，以 Docker 镜像为载体，包含所有运行时依赖（数据库、Redis、Git、前端），实现一键运行完整测试套件。

**测试范围**：
- 后端 API 集成测试（pytest）：HTTP 请求走真实网络，测真实数据库 + Redis + Git 操作
- 前端 E2E 测试（Playwright）：真实浏览器 headless 模式，测 UI 交互流程
- Feature 完整状态机流程：brainstorming → planning → implementing → testing → reviewing → approved → verifying → merged
- LLM/Agent 层使用 mock，不调用真实 API

---

## 2. 架构概览

```
solo100-test 镜像（单一测试镜像）
├── 基础镜像：python:3.11-slim + Node.js 20
├── 服务层
│   ├── Redis（redis-server，容器内启动）
│   ├── Backend（uvicorn，port 8000）
│   └── Frontend（next start，port 3000）
├── 数据层
│   ├── SQLite（真实文件 /tmp/solo100-test.db）
│   └── 临时 Git repo（entrypoint 动态创建，测试后销毁）
├── Mock 层
│   └── LLM/Agent mock（pytest fixture / 环境变量注入）
└── 测试执行层
    ├── pytest tests/integration/
    └── playwright test
```

---

## 3. 文件结构

```
solo100/
├── Dockerfile.test              # 测试专用镜像
├── entrypoint-test.sh           # 启动脚本
├── backend/
│   ├── tests/
│   │   ├── unit/                # 现有单元测试（不变）
│   │   └── integration/          # 新增集成测试
│   │       ├── conftest.py       # 真实 DB + Redis + Git repo fixture
│   │       ├── test_projects.py
│   │       ├── test_features.py
│   │       └── test_feature_workflow.py  # 完整状态机流程
│   └── agents/
│       └── mock_agent.py        # Mock ClaudeCodeAgent（固定响应）
└── frontend/
    └── tests/
        └── e2e/                 # Playwright E2E
            ├── playwright.config.ts
            ├── conftest.ts
            ├── projects.spec.ts
            └── feature-workflow.spec.ts
```

---

## 4. 启动流程（entrypoint-test.sh）

```
#!/bin/bash
set -e

# 1. 初始化临时 Git repo（作为"远程仓库"供测试使用）
git init --bare /tmp/test-remote.git

# 2. 启动 Redis
redis-server --daemonize yes

# 3. 初始化数据库 schema
cd /app
PYTHONPATH=/app alembic upgrade head

# 4. 启动 backend（后台，等待 health 就绪）
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
wait-for-it localhost:8000 --timeout=30 -- echo "Backend ready"

# 5. 构建前端（预构建，不启动 dev server）
cd /frontend
npm run build
PORT=3000 npx next start -p 3000 &
FRONTEND_PID=$!
wait-for-it localhost:3000 --timeout=60 -- echo "Frontend ready"

# 6. 运行后端集成测试
cd /app
pytest tests/integration/ -v --tb=short
BACKEND_RESULT=$?

# 7. 运行前端 E2E 测试
cd /frontend
npx playwright test
PLAYWRIGHT_RESULT=$?

# 8. 汇总结果
if [ $BACKEND_RESULT -ne 0 ] || [ $PLAYWRIGHT_RESULT -ne 0 ]; then
    echo "TESTS FAILED"
    exit 1
fi
echo "ALL TESTS PASSED"
exit 0
```

---

## 5. 后端集成测试设计

### 5.1 conftest.py（共享 fixture）

```python
# tests/integration/conftest.py
import os, tempfile, subprocess
import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine

TEST_DB = "/tmp/solo100-test.db"
TEST_GIT_REMOTE = "/tmp/test-remote.git"

@pytest.fixture(scope="session", autouse=True)
def setup_git_repo():
    """创建临时 bare Git repo"""
    os.makedirs(TEST_GIT_REMOTE, exist_ok=True)
    subprocess.run(["git", "init", "--bare", TEST_GIT_REMOTE], cwd="/tmp", check=True)
    yield
    # teardown: 测试结束后销毁

@pytest.fixture(scope="session")
def db_engine():
    """真实 SQLite 文件数据库"""
    engine = create_engine(f"sqlite:///{TEST_DB}")
    from app.database import Base
    Base.metadata.create_all(engine)
    yield engine
    os.remove(TEST_DB)

# Mock Agent fixture
@pytest.fixture
def mock_agent():
    from tests.integration.mock_agent import MockClaudeCodeAgent
    return MockClaudeCodeAgent()
```

### 5.2 MockClaudeCodeAgent

固定返回结构化结果，不调用真实 LLM API：

```python
# tests/integration/mock_agent.py
class MockClaudeCodeAgent:
    async def brainstorm(self, feature, previous=None, failure_reason=None):
        return BrainstormResult(
            summary="Mock: 分析完成",
            key_points=["点1", "点2"],
            tech_approach="使用 Python 实现"
        )

    async def plan(self, feature, brainstorm, previous_plan=None):
        return Plan(steps=[
            PlanStep(title="步骤1", description="实现基础结构", files=["a.py"]),
            PlanStep(title="步骤2", description="实现核心逻辑", files=["b.py"]),
        ])

    async def implement(self, feature, plan, worktree_path):
        # 在 worktree_path 中写入计划中的文件
        return ImplementResult(files_changed=2, commits=1)

    async def review(self, feature):
        return ReviewResult(issues=[], approved=True)
```

### 5.3 测试用例覆盖

| 测试文件 | 覆盖场景 |
|---|---|
| `test_projects.py` | 创建 Project、查询、删除 |
| `test_features.py` | 创建 Feature、状态流转 CRUD |
| `test_feature_workflow.py` | 完整状态机：pending → merged，含 retry 和回溯 |

---

## 6. 前端 E2E 测试设计

### 6.1 Playwright 配置

```typescript
// tests/e2e/playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  use: {
    baseURL: 'http://localhost:3000',
    headless: true,
  },
  webServer: undefined, // 由 entrypoint-test.sh 统一管理
});
```

### 6.2 测试用例覆盖

| 测试文件 | 覆盖场景 |
|---|---|
| `projects.spec.ts` | 创建项目、查看列表 |
| `feature-workflow.spec.ts` | 创建 Feature、启动开发、人工介入节点操作、查看日志 |

---

## 7. 集成测试 vs 单元测试对比

| | 单元测试 | 集成测试 |
|---|---|---|
| 数据库 | in-memory SQLite | 真实 SQLite 文件 |
| Redis | mock | 真实 redis-server |
| Git | mock | 真实 git 操作 |
| LLM/Agent | mock | mock（固定响应）|
| HTTP | ASGITransport（不走网络）| 真实 HTTP（localhost:8000）|
| 浏览器 | 无 | Playwright Chromium headless |

---

## 8. Dockerfile.test

```dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl redis-server nodejs npm wait-for-it \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
RUN pip install --no-cache-dir playwright && playwright install --with-deps chromium

# 安装 Node 依赖
COPY frontend/package.json /frontend/package.json
COPY frontend/package-lock.json /frontend/package-lock.json
RUN cd /frontend && npm ci

# 复制源码
COPY backend/ /app
COPY frontend/ /frontend

# 非 root 用户
RUN useradd --create-home --shell /bin/bash testuser
USER testuser

COPY entrypoint-test.sh /entrypoint-test.sh
RUN chmod +x /entrypoint-test.sh

WORKDIR /app

CMD ["/entrypoint-test.sh"]
```

---

## 9. 运行方式

```bash
# 构建镜像
docker build -f Dockerfile.test -t solo100-test .

# 运行测试
docker run --rm solo100-test

# 或本地运行（需先启动 Redis）
redis-server --daemonize yes
./entrypoint-test.sh
```

---

## 10. 依赖环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `ANTHROPIC_API_KEY` | LLM API Key（mock 模式下不必须） | `test_key` |
| `DATABASE_URL` | 数据库连接 | `sqlite+aiosqlite:////tmp/solo100-test.db` |
| `REDIS_URL` | Redis 连接 | `redis://localhost:6379` |
| `SECRET_KEY` | FastAPI secret | `test-secret-key` |
