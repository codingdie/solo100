#!/bin/bash
set -euo pipefail

export TZ=Asia/Shanghai

echo "=== [1/8] 初始化临时 Git bare repo ==="
mkdir -p /tmp/solo100-test-remote.git
if [ ! -f /tmp/solo100-test-remote.git/config ]; then
    git init --bare /tmp/solo100-test-remote.git
fi

echo "=== [2/8] 启动 Redis ==="
redis-server --daemonize yes --loglevel warning

echo "=== [3/8] 初始化数据库 ==="
cd /app/backend
export PYTHONPATH=/app/backend
python3 -c "
import asyncio
from app.database import engine, Base
from app.models import AgentConfig, Feature, FeatureExecution, Project, ReviewReport
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())
"

echo "=== [4/8] 启动 Backend ==="
cd /app/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
wait-for-it localhost:8000 --timeout=30 -- echo "Backend ready"
echo "Backend PID: $BACKEND_PID"

echo "=== [5/8] 构建前端 ==="
cd /frontend
npm run build

echo "=== [6/8] 启动 Frontend ==="
PORT=3000 npx next start -p 3000 &
FRONTEND_PID=$!
wait-for-it localhost:3000 --timeout=60 -- echo "Frontend port ready"
# 等待 Next.js 真正就绪（HTTP 200）
for i in $(seq 1 30); do
  if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "Frontend ready"
    break
  fi
  sleep 1
done
echo "Frontend PID: $FRONTEND_PID"

echo "=== [7/8] 运行后端测试（单元测试 + 集成测试）==="
cd /app/backend
export PYTHONPATH=/app/backend
export REDIS_URL=redis://localhost:6379
export DATABASE_URL=sqlite+aiosqlite:///./test.db
export ANTHROPIC_API_KEY=test_key
# 集成测试环境变量
export TEST_DATABASE_PATH=/tmp/solo100-integration.db
export TEST_GIT_REMOTE=/tmp/solo100-test-remote.git
export TEST_WORKTREE_ROOT=/tmp/solo100-test-worktrees
pytest tests/ -v --tb=short --color=yes
BACKEND_RESULT=$?

echo "=== [8/8] 运行前端 E2E 测试 ==="
cd /frontend
npx playwright test --config=tests/e2e/playwright.config.ts
PLAYWRIGHT_RESULT=$?

# 清理后台进程
kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true

# 汇总结果
if [ $BACKEND_RESULT -ne 0 ] || [ $PLAYWRIGHT_RESULT -ne 0 ]; then
    echo ""
    echo "TESTS FAILED"
    echo "  Backend result: $BACKEND_RESULT"
    echo "  Playwright result: $PLAYWRIGHT_RESULT"
    exit 1
fi
echo ""
echo "ALL TESTS PASSED"
exit 0
