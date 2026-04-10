# solo100 项目说明

设计文档：`docs/superpowers/specs/2026-03-25-solo100-design.md`

---

## 开发规范

### 代码风格
- 后端：Python，遵循 PEP 8，使用类型注解
- 前端：TypeScript，2 空格缩进
- 注释：中文/英文双语

### Git 规范
- commit message 中英文双语，英文在前，格式如下：

```
<type>: <English description>

<中文描述>
```

示例：
```
feat: add Feature state machine executor with retry and rollback support

添加 Feature 状态机驱动逻辑，支持回溯和重试
```

- 不要自动提交，等待用户明确说"提交"或"commit"
- commit message 不加 Co-Authored-By 标签

---

## 测试规范

### 强制要求：必须用 Docker 运行全部测试

每次修改代码后，必须通过以下命令构建镜像并运行全部测试（单元测试 + 集成测试 + E2E 测试）：

```bash
# 构建测试镜像
docker build -f Dockerfile.test -t solo100-test .

# 运行全部测试
docker run --rm solo100-test
```

- 测试全部通过（exit 0）才算完成
- 禁止跳过 Docker 测试直接提交代码
- 测试镜像包含：Python 单元测试、集成测试（真实 DB + Redis + Backend）、前端 E2E 测试（Playwright）

### 测试结构

| 层级 | 路径 | 说明 |
|------|------|------|
| 单元测试 | `backend/tests/unit/` | Mock 外部依赖，内存数据库 |
| 集成测试 | `backend/tests/integration/` | 真实 HTTP + SQLite + Git |
| E2E 测试 | `frontend/tests/e2e/` | Playwright，真实前后端 |

### 测试入口

- Docker 测试入口脚本：`entrypoint-test.sh`
- 测试镜像定义：`Dockerfile.test`

