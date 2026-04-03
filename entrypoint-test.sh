#!/bin/bash
set -euo pipefail

export TZ=Asia/Shanghai

echo "=== [1/8] 初始化临时 Git bare repo ==="
mkdir -p /tmp/solo100-test-remote.git
if [ ! -d /tmp/solo100-test-remote.git/HEAD ]; then
    git init --bare /tmp/solo100-test-remote.git
fi

echo "=== [2/8] 启动 Redis ==="
redis-server --daemonize yes --loglevel warning

echo "=== [3/8] 初始化数据库 ==="
cd /app
export PYTHONPATH=/app
alembic upgrade head

echo "=== [4/8] 启动 Backend ==="
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
wait-for-it localhost:3000 --timeout=60 -- echo "Frontend ready"
echo "Frontend PID: $FRONTEND_PID"

echo "=== [7/8] 运行后端集成测试 ==="
cd /app
export PYTHONPATH=/app
export ANTHROPIC_API_KEY=test_key
pytest tests/integration/ -v --tb=short --color=yes
BACKEND_RESULT=$?

echo "=== [8/8] 运行前端 E2E 测试 ==="
cd /frontend
npx playwright test
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
