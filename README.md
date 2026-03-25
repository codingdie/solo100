# solo100

[English](README.en.md) | 中文

> 在 AI 时代，让一个工程师拥有团队的开发速度。

solo100 是一个 AI 驱动的开发工作流平台。通过标准 Git Flow + 多 AI Agent 并行执行，单人开发者可以模拟多人团队协作的开发节奏，实现 100 倍效率提升。

---

## 核心理念

现有的 AI 编程工具（如 Claude Code）在单个任务上表现出色，但在大型项目中，单个 Agent 串行执行的速度依然有限。solo100 的思路是：

- 将需求拆解成可并行的独立 Feature
- 每个 Feature 由独立的 AI Agent 按完整开发工作流执行
- 人工在关键节点介入确认，保持对质量的控制
- 最终通过标准 PR + Code Review 流程合并代码

---

## 功能特性

### 需求管理
- 输入大需求，AI 自动拆解成独立 Feature 列表
- 人工审查调整，按需启动开发

### Feature 开发流程
每个 Feature 独立走完整开发流程，共 4 个人工介入节点：

```
brainstorming → planning → implementing → testing → reviewing → merge
      ↑                                                  |
      └──────────────── 可回溯（增量修改）────────────────┘
```

1. **确认 brainstorming** — AI 分析需求，人工确认理解是否正确
2. **确认实现计划** — AI 生成开发计划，人工审查方案
3. **确认测试结果** — 执行测试，人工查看报告决定是否继续
4. **Approve / Reject** — AI code review 完成，人工最终决定是否合并

### 多 Feature 并行
多个 Feature 同时执行，各自在独立 Git branch 上开发，互不干扰。

### 双入口操作
- **Web UI** — 浏览器完整操作界面，实时进度监控
- **飞书** — 消息卡片操作所有介入节点，手机上也能用

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui |
| 后端 | Python FastAPI + SQLAlchemy |
| 任务队列 | Celery + Redis |
| 数据库 | SQLite |
| Git 操作 | GitPython |
| 部署 | Docker Compose |

---

## 快速开始

```bash
# 克隆项目
git clone git@github.com:codingdie/solo100.git
cd solo100

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 SSH 私钥、API Key 等配置

# 启动服务
docker compose up -d

# 访问 Web UI
open http://localhost:3000
```

---

## 版本规划

| 版本 | 功能 | 状态 |
|------|------|------|
| v0.1 | Web UI + 单 Feature 完整开发流程 + Claude Code | 开发中 |
| v0.2 | 需求管理 + FeaturePlanner | 计划中 |
| v0.3 | 多 Feature 并行执行 | 计划中 |
| v0.4 | 飞书双向集成 | 计划中 |
| v0.5 | 多 Agent 支持（Codex 等） | 计划中 |

---

## 文档

- [系统设计文档](docs/superpowers/specs/2026-03-25-solo100-design.md)
- [v0.1 详细设计](docs/superpowers/specs/2026-03-26-v0.1-design.md)

---

## License

MIT
