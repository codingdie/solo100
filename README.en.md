# solo100

中文 | [English](README.en.md)

> Give a solo engineer the velocity of a team, in the age of AI.

solo100 is an AI-driven development workflow platform. By combining standard Git Flow with parallel AI Agent execution, a solo developer can match the pace of a multi-person team — achieving 100x productivity.

---

## The Idea

Existing AI coding tools (like Claude Code) excel at individual tasks, but in large projects, a single agent running serially is still slow. solo100's approach:

- Break requirements into independently parallelizable Features
- Each Feature is executed by a dedicated AI Agent following a complete development workflow
- Humans intervene at key checkpoints to maintain quality control
- Code is merged through standard PR + Code Review process

---

## Features

### Requirement Management
- Input a high-level requirement, AI automatically breaks it down into independent Features
- Human review and adjustment, start development on demand

### Feature Development Workflow
Each Feature runs through a complete development pipeline with 4 human checkpoints:

```
brainstorming → planning → implementing → testing → reviewing → merge
      ↑                                                  |
      └──────────────── retryable (incremental) ─────────┘
```

1. **Confirm brainstorming** — AI analyzes the requirement, human confirms understanding
2. **Confirm implementation plan** — AI generates a dev plan, human reviews the approach
3. **Confirm test results** — Tests run, human reviews the report and decides whether to proceed
4. **Approve / Reject** — AI code review complete, human makes the final merge decision

### Parallel Feature Execution
Multiple Features run simultaneously, each on its own isolated Git branch.

### Dual Entry Points
- **Web UI** — Full browser interface with real-time progress monitoring
- **Feishu (Lark)** — Message card interactions for all checkpoints, works on mobile

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python FastAPI + SQLAlchemy |
| Task Queue | Celery + Redis |
| Database | SQLite |
| Git Operations | GitPython |
| Deployment | Docker Compose |

---

## Quick Start

```bash
# Clone the repo
git clone git@github.com:codingdie/solo100.git
cd solo100

# Configure environment
cp .env.example .env
# Edit .env — fill in SSH keys, API keys, etc.

# Start services
docker compose up -d

# Open Web UI
open http://localhost:3000
```

---

## Roadmap

| Version | Features | Status |
|---------|----------|--------|
| v0.1 | Web UI + single Feature full workflow + Claude Code | In progress |
| v0.2 | Requirement management + FeaturePlanner | Planned |
| v0.3 | Parallel Feature execution | Planned |
| v0.4 | Feishu (Lark) two-way integration | Planned |
| v0.5 | Multi-Agent support (Codex, etc.) | Planned |

---

## Docs

- [System Design](docs/superpowers/specs/2026-03-25-solo100-design.md)
- [v0.1 Detailed Design](docs/superpowers/specs/2026-03-26-v0.1-design.md)

---

## License

MIT
