I now have a thorough understanding of the codebase. Let me produce the complete Plan 3 document.

---

# solo100 Agent & Git 层实现计划

**文档路径**: `docs/superpowers/plans/2026-03-26-plan-3-agent-git-layer.md`
**版本**: v0.1 Agent & Git Layer
**日期**: 2026-03-26
**前置依赖**: [Plan 1 - Backend Foundation](./2026-03-26-plan-1-backend-foundation.md) + [Plan 2 - State Machine Core](./2026-03-26-plan-2-state-machine-core.md)

---

## Goal

替换 Plan 2 中所有 Stub 实现，交付真实可运行的 Agent & Git 层：

1. `BaseAgent` 抽象接口 + `ClaudeCodeAgent`（通过 `subprocess.Popen` 调用 Claude Code CLI）
2. `GitManager`（通过 `gitpython` 封装 clone / branch / worktree / commit / PR / rebase / merge / cleanup）
3. `ReviewEngine`（通过 `httpx` 调用 Anthropic API 生成结构化 code review 报告）
4. 将 `FeatureExecutor` 中的 stub 调用替换为真实 Agent + Git 调用

---

## Architecture

```
backend/app/
├── agents/
│   ├── base.py              # BaseAgent 抽象类（brainstorm / plan / implement）
│   └── claude_code.py       # ClaudeCodeAgent：subprocess.Popen 调用 claude CLI
│
├── services/
│   ├── git_manager.py       # 替换 Stub → 真实 GitPython 实现
│   ├── review_engine.py     # 替换 Stub → 真实 Anthropic API 调用
│   └── feature_executor.py  # 修改：注入真实 Agent + GitManager
│
└── tests/unit/
    ├── test_base_agent.py
    ├── test_claude_code_agent.py
    ├── test_git_manager.py
    └── test_review_engine.py
```

**数据流**：

```
FeatureExecutor._run_brainstorming()
    │
    └── ClaudeCodeAgent.brainstorm(feature, previous, failure_reason)
            │
            ├── 构造 prompt（内嵌模板）
            ├── subprocess.Popen(["claude", "--print", prompt])
            ├── 实时读取 stdout → notify_log() → WebSocket
            └── 解析 ```json ... ``` 块 → BrainstormResult

FeatureExecutor._run_implementing()
    │
    ├── GitManager.clone(ssh_url, target_dir, ssh_key_env)
    │       └── GIT_SSH_COMMAND=ssh -i /tmp/solo100_ssh_{id}.key
    ├── GitManager.create_branch(repo_path, branch_name)
    ├── GitManager.create_worktree(repo_path, branch_name, worktree_path)
    ├── ClaudeCodeAgent.implement(feature, plan, worktree_path)
    └── GitManager.commit(worktree_path, message, files)

FeatureExecutor._run_reviewing()
    │
    └── ReviewEngine.review(feature, git_manager)
            ├── git diff main...HEAD → diff_text
            ├── httpx.post(Anthropic API, prompt=diff_text)
            └── 解析 JSON → ReviewReportResult → 写入 ReviewReport 表
```

---

## Tech Stack

| 组件 | 技术 |
|------|------|
| Agent CLI 调用 | `subprocess.Popen`，`asyncio.create_subprocess_exec` |
| Git 操作 | `gitpython==3.1.41` |
| HTTP Client | `httpx==0.26.0`（async，已在 requirements.txt） |
| SSH 密钥管理 | 写入 `/tmp/solo100_ssh_{feature_id}.key`，chmod 600，用完即删 |
| JSON 解析 | `re` 正则提取 ` ```json ... ``` ` 块 |
| 测试 | `pytest`, `pytest-asyncio`, `unittest.mock` |
| Anthropic 模型 | `claude-sonnet-4-6` |

---

## 前置条件

Plan 1 和 Plan 2 必须已完成并提交。以下文件必须存在：

```
backend/app/services/git_manager.py       # GitManagerStub（本次替换）
backend/app/services/review_engine.py     # ReviewEngineStub（本次替换）
backend/app/services/stage_results.py     # BrainstormResult / Plan / ImplementResult
backend/app/services/feature_executor.py  # FeatureExecutor（本次修改注入点）
backend/app/services/notification_hub.py  # notify_log()
backend/app/config.py                     # settings.anthropic_api_key_env
backend/requirements.txt                  # httpx, gitpython 需要添加
```

---

## Task 1: 更新依赖

**Files**
- 修改: `backend/requirements.txt`

### 步骤 1.1 在 `backend/requirements.txt` 中添加 gitpython

在现有 requirements.txt 的 `# Utilities` 区块前添加：

```
# Git operations
gitpython==3.1.41

# SSH key temp file handling (stdlib os/stat, no extra dep needed)
```

同时确认 `httpx==0.26.0` 已存在（Plan 1 已添加）。

**Commit:**

```bash
git add backend/requirements.txt
git commit -m "chore: add gitpython dependency for real Git operations

添加 gitpython==3.1.41，用于 Plan 3 GitManager 真实实现
"
```

---

## Task 2: BaseAgent 接口

**Files**
- 创建: `backend/app/agents/__init__.py`
- 创建: `backend/app/agents/base.py`
- 创建: `backend/tests/unit/test_base_agent.py`

### 步骤 2.1 创建 `backend/app/agents/__init__.py`

```python
"""Agent implementations package."""

from app.agents.base import BaseAgent
from app.agents.claude_code import ClaudeCodeAgent

__all__ = ["BaseAgent", "ClaudeCodeAgent"]
```

### 步骤 2.2 创建 `backend/app/agents/base.py`

```python
"""BaseAgent abstract interface.

All Agent implementations (ClaudeCodeAgent, future Codex agent, etc.)
must subclass BaseAgent and implement the three stage methods.
"""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable

from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


# Type alias for the log callback: receives a single log line string
LogCallback = Callable[[str], Awaitable[None]]


class BaseAgent(ABC):
    """Abstract base class for all AI Agent implementations.

    Each agent must implement three pipeline stage methods:
      - brainstorm: analyse the feature and produce acceptance criteria
      - plan: produce a structured implementation plan
      - implement: write code in the given worktree

    All methods accept an optional `notify_log` callback that is called
    with each line of agent output so callers can stream it to WebSocket.
    """

    @abstractmethod
    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> BrainstormResult:
        """Analyse the feature and produce a BrainstormResult.

        Args:
            feature: The Feature ORM object (title + description).
            previous: Result from the previous brainstorming attempt, if any.
            failure_reason: Why the previous attempt failed, if any.
            notify_log: Async callback invoked with each stdout line.

        Returns:
            BrainstormResult with analysis, acceptance_criteria, key_points,
            and estimated_risk.
        """
        ...

    @abstractmethod
    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log: LogCallback | None = None,
    ) -> Plan:
        """Produce a structured implementation plan.

        Args:
            feature: The Feature ORM object.
            brainstorm: The approved BrainstormResult from the previous stage.
            previous_plan: Plan from the previous attempt, if any.
            notify_log: Async callback invoked with each stdout line.

        Returns:
            Plan with tasks list, estimated_risk, and raw_output.
        """
        ...

    @abstractmethod
    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log: LogCallback | None = None,
    ) -> ImplementResult:
        """Write code in the given worktree according to the plan.

        Args:
            feature: The Feature ORM object.
            plan: The approved Plan from the previous stage.
            worktree_path: Absolute path to the git worktree directory.
            notify_log: Async callback invoked with each stdout line.

        Returns:
            ImplementResult with files_changed, summary, and commit_hash.
        """
        ...
```

### 步骤 2.3 创建 `backend/tests/unit/test_base_agent.py`

```python
"""Unit tests for BaseAgent interface contract."""

import pytest

from app.agents.base import BaseAgent, LogCallback
from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


class ConcreteAgent(BaseAgent):
    """Minimal concrete implementation for testing the interface."""

    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> BrainstormResult:
        return BrainstormResult(
            analysis="test analysis",
            acceptance_criteria=["AC1"],
        )

    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log: LogCallback | None = None,
    ) -> Plan:
        return Plan(tasks=[{"title": "task1", "file_patterns": [], "description": "d"}])

    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log: LogCallback | None = None,
    ) -> ImplementResult:
        return ImplementResult(files_changed=[], summary="done")


def test_base_agent_is_abstract() -> None:
    """BaseAgent cannot be instantiated directly."""
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


def test_concrete_agent_instantiates() -> None:
    """A concrete subclass with all methods implemented can be instantiated."""
    agent = ConcreteAgent()
    assert isinstance(agent, BaseAgent)


@pytest.mark.asyncio
async def test_concrete_agent_brainstorm_returns_result() -> None:
    """Concrete brainstorm() returns a BrainstormResult."""
    agent = ConcreteAgent()
    # Feature is a SQLAlchemy model; use a simple mock-like object
    class FakeFeature:
        id = "feat-001"
        title = "Test Feature"
        description = "Test description"

    result = await agent.brainstorm(FakeFeature())  # type: ignore[arg-type]
    assert isinstance(result, BrainstormResult)
    assert result.analysis == "test analysis"
    assert result.acceptance_criteria == ["AC1"]


@pytest.mark.asyncio
async def test_concrete_agent_plan_returns_plan() -> None:
    """Concrete plan() returns a Plan."""
    agent = ConcreteAgent()

    class FakeFeature:
        id = "feat-001"
        title = "Test Feature"
        description = "Test description"

    brainstorm = BrainstormResult(analysis="a", acceptance_criteria=["AC1"])
    result = await agent.plan(FakeFeature(), brainstorm)  # type: ignore[arg-type]
    assert isinstance(result, Plan)
    assert len(result.tasks) == 1


@pytest.mark.asyncio
async def test_notify_log_callback_is_optional() -> None:
    """All stage methods must work without a notify_log callback."""
    agent = ConcreteAgent()

    class FakeFeature:
        id = "feat-001"
        title = "Test Feature"
        description = "Test description"

    result = await agent.brainstorm(FakeFeature(), notify_log=None)  # type: ignore[arg-type]
    assert result is not None
```

**Commit:**

```bash
git add backend/app/agents/__init__.py \
         backend/app/agents/base.py \
         backend/tests/unit/test_base_agent.py
git commit -m "feat: add BaseAgent abstract interface with brainstorm/plan/implement

添加 agents/base.py：BaseAgent ABC 定义三个阶段方法签名（brainstorm/plan/implement），
含 LogCallback 类型别名；agents/__init__.py 导出；test_base_agent.py 验证接口约束
"
```

---

## Task 3: ClaudeCodeAgent 实现

**Files**
- 创建: `backend/app/agents/claude_code.py`
- 创建: `backend/tests/unit/test_claude_code_agent.py`

### 步骤 3.1 创建 `backend/app/agents/claude_code.py`

```python
"""ClaudeCodeAgent — calls the Claude Code CLI via subprocess.

Execution model:
  - Uses asyncio.create_subprocess_exec to run `claude --print <prompt>`
  - Reads stdout line-by-line, calling notify_log for each line
  - After process exits, parses the full output for a ```json ... ``` block
  - Deserialises the JSON block into the appropriate result dataclass
  - Raises AgentError on timeout, non-zero exit code, or parse failure

Prompt templates are embedded in this file (no external config files).
"""

import asyncio
import json
import logging
import os
import re
from typing import Any

from app.agents.base import BaseAgent, LogCallback
from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan

logger = logging.getLogger(__name__)

# Default timeout in seconds for each Claude Code invocation
DEFAULT_TIMEOUT = 300

# Regex to extract the first ```json ... ``` block from agent output
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```", re.MULTILINE)


class AgentError(Exception):
    """Raised when the agent fails to produce a valid result."""
    pass


class AgentTimeoutError(AgentError):
    """Raised when the agent process exceeds the timeout."""
    pass


class AgentParseError(AgentError):
    """Raised when the agent output cannot be parsed into the expected structure."""
    pass


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_BRAINSTORM_PROMPT_TEMPLATE = """\
You are a senior software engineer performing a feature analysis.

## Feature
Title: {title}
Description:
{description}

{previous_section}

## Task
Analyse this feature thoroughly. Identify:
1. What needs to be built (technical analysis)
2. Acceptance criteria (concrete, testable conditions)
3. Key implementation points (architecture decisions, risks)
4. Estimated risk level: low | medium | high

## Output Format
Respond with ONLY a JSON code block in this exact format:

```json
{{
  "analysis": "<detailed technical analysis>",
  "acceptance_criteria": ["<criterion 1>", "<criterion 2>"],
  "key_points": ["<point 1>", "<point 2>"],
  "estimated_risk": "low|medium|high"
}}
```
"""

_PLAN_PROMPT_TEMPLATE = """\
You are a senior software engineer creating an implementation plan.

## Feature
Title: {title}
Description:
{description}

## Brainstorming Analysis
{analysis}

## Acceptance Criteria
{acceptance_criteria}

{previous_plan_section}

## Task
Create a detailed, ordered implementation plan. Each task should:
- Have a clear title
- List the file patterns it will touch (glob patterns)
- Have a concise description of what to implement

## Output Format
Respond with ONLY a JSON code block in this exact format:

```json
{{
  "tasks": [
    {{
      "title": "<task title>",
      "file_patterns": ["<glob pattern>"],
      "description": "<what to implement>"
    }}
  ],
  "estimated_risk": "low|medium|high"
}}
```
"""

_IMPLEMENT_PROMPT_TEMPLATE = """\
You are a senior software engineer implementing a feature.

## Feature
Title: {title}
Description:
{description}

## Implementation Plan
{plan_tasks}

## Working Directory
{worktree_path}

## Task
Implement ALL tasks in the plan above. Work in the directory: {worktree_path}

Rules:
- Write complete, production-quality code
- Follow existing code style and conventions in the repository
- Add appropriate tests for new functionality
- Do NOT commit — only write the files

After completing all tasks, output a summary in this exact format:

```json
{{
  "files_changed": ["<relative path 1>", "<relative path 2>"],
  "summary": "<brief description of what was implemented>"
}}
```
"""


# ---------------------------------------------------------------------------
# ClaudeCodeAgent
# ---------------------------------------------------------------------------


class ClaudeCodeAgent(BaseAgent):
    """Agent implementation that calls the Claude Code CLI.

    The `claude` binary must be available in PATH and authenticated
    (ANTHROPIC_API_KEY must be set in the environment).
    """

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        claude_bin: str = "claude",
    ) -> None:
        """
        Args:
            timeout: Maximum seconds to wait for each CLI invocation.
            claude_bin: Path or name of the claude CLI binary.
        """
        self._timeout = timeout
        self._claude_bin = claude_bin

    # -------------------------------------------------------------------------
    # Public stage methods
    # -------------------------------------------------------------------------

    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> BrainstormResult:
        """Run the brainstorming stage via Claude Code CLI."""
        previous_section = ""
        if previous is not None:
            previous_section = (
                f"## Previous Brainstorming Result\n"
                f"{previous.analysis}\n\n"
                f"## Failure Reason\n"
                f"{failure_reason or 'Not specified'}\n\n"
                f"Please improve on the previous analysis, addressing the failure reason."
            )

        prompt = _BRAINSTORM_PROMPT_TEMPLATE.format(
            title=feature.title,
            description=feature.description,
            previous_section=previous_section,
        )

        output = await self._run_claude(prompt, notify_log=notify_log)
        data = self._parse_json_block(output, stage="brainstorm")

        return BrainstormResult(
            analysis=data.get("analysis", ""),
            acceptance_criteria=data.get("acceptance_criteria", []),
            key_points=data.get("key_points", []),
            estimated_risk=data.get("estimated_risk", "medium"),
        )

    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log: LogCallback | None = None,
    ) -> Plan:
        """Run the planning stage via Claude Code CLI."""
        previous_plan_section = ""
        if previous_plan is not None:
            tasks_str = json.dumps(previous_plan.tasks, indent=2, ensure_ascii=False)
            previous_plan_section = (
                f"## Previous Plan (for reference — improve on it)\n"
                f"```json\n{tasks_str}\n```\n"
            )

        prompt = _PLAN_PROMPT_TEMPLATE.format(
            title=feature.title,
            description=feature.description,
            analysis=brainstorm.analysis,
            acceptance_criteria="\n".join(
                f"- {c}" for c in brainstorm.acceptance_criteria
            ),
            previous_plan_section=previous_plan_section,
        )

        output = await self._run_claude(prompt, notify_log=notify_log)
        data = self._parse_json_block(output, stage="plan")

        return Plan(
            tasks=data.get("tasks", []),
            estimated_risk=data.get("estimated_risk", "medium"),
            raw_output=output,
        )

    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log: LogCallback | None = None,
    ) -> ImplementResult:
        """Run the implementation stage via Claude Code CLI."""
        tasks_str = "\n".join(
            f"{i + 1}. **{t.get('title', '')}**\n"
            f"   Files: {', '.join(t.get('file_patterns', []))}\n"
            f"   {t.get('description', '')}"
            for i, t in enumerate(plan.tasks)
        )

        prompt = _IMPLEMENT_PROMPT_TEMPLATE.format(
            title=feature.title,
            description=feature.description,
            plan_tasks=tasks_str,
            worktree_path=worktree_path,
        )

        output = await self._run_claude(
            prompt,
            cwd=worktree_path,
            notify_log=notify_log,
        )
        data = self._parse_json_block(output, stage="implement")

        return ImplementResult(
            files_changed=data.get("files_changed", []),
            summary=data.get("summary", ""),
            commit_hash=None,  # Commit is handled by GitManager, not the agent
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _run_claude(
        self,
        prompt: str,
        cwd: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> str:
        """Invoke the claude CLI and return the full stdout as a string.

        Args:
            prompt: The prompt text to pass via --print flag.
            cwd: Working directory for the subprocess (used in implement stage).
            notify_log: Async callback called with each stdout line.

        Returns:
            Full stdout output as a single string.

        Raises:
            AgentTimeoutError: If the process exceeds self._timeout seconds.
            AgentError: If the process exits with a non-zero return code.
        """
        cmd = [self._claude_bin, "--print", prompt]
        logger.info(
            "ClaudeCodeAgent: launching %s (cwd=%s, timeout=%ds)",
            self._claude_bin,
            cwd,
            self._timeout,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            raise AgentError(
                f"Claude Code CLI not found: '{self._claude_bin}'. "
                f"Ensure it is installed and in PATH."
            ) from exc

        lines: list[str] = []

        async def _read_stdout() -> None:
            assert proc.stdout is not None
            async for raw_line in proc.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                lines.append(line)
                if notify_log is not None:
                    try:
                        await notify_log(line)
                    except Exception:
                        pass  # Never let log callback failures kill the agent

        try:
            await asyncio.wait_for(
                _read_stdout(),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise AgentTimeoutError(
                f"Claude Code CLI timed out after {self._timeout}s"
            )

        await proc.wait()

        if proc.returncode != 0:
            stderr_bytes = b""
            if proc.stderr is not None:
                stderr_bytes = await proc.stderr.read()
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")
            raise AgentError(
                f"Claude Code CLI exited with code {proc.returncode}. "
                f"stderr: {stderr_text[:500]}"
            )

        return "\n".join(lines)

    @staticmethod
    def _parse_json_block(output: str, stage: str) -> dict[str, Any]:
        """Extract and parse the first ```json ... ``` block from agent output.

        Args:
            output: Full stdout from the claude CLI.
            stage: Stage name for error messages.

        Returns:
            Parsed dict from the JSON block.

        Raises:
            AgentParseError: If no JSON block is found or JSON is invalid.
        """
        match = _JSON_BLOCK_RE.search(output)
        if match is None:
            raise AgentParseError(
                f"No ```json ... ``` block found in {stage} output. "
                f"Output (first 500 chars): {output[:500]}"
            )

        json_text = match.group(1).strip()
        try:
            return json.loads(json_text)
        except json.JSONDecodeError as exc:
            raise AgentParseError(
                f"Invalid JSON in {stage} output: {exc}. "
                f"JSON text: {json_text[:300]}"
            ) from exc
```

### 步骤 3.2 创建 `backend/tests/unit/test_claude_code_agent.py`

```python
"""Unit tests for ClaudeCodeAgent."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.claude_code import (
    AgentError,
    AgentParseError,
    AgentTimeoutError,
    ClaudeCodeAgent,
)
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeFeature:
    """Minimal Feature-like object for testing."""
    id = "feat-test-001"
    title = "Add user authentication"
    description = "Implement OAuth2 login and logout."


def _make_brainstorm_output(data: dict) -> str:
    return f"Some preamble text\n```json\n{json.dumps(data)}\n```\nSome trailing text"


def _make_plan_output(data: dict) -> str:
    return f"Planning output\n```json\n{json.dumps(data)}\n```"


def _make_implement_output(data: dict) -> str:
    return f"Implementation complete\n```json\n{json.dumps(data)}\n```"


# ---------------------------------------------------------------------------
# _parse_json_block
# ---------------------------------------------------------------------------


class TestParseJsonBlock:
    def test_extracts_json_block(self) -> None:
        output = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"key": "value"}

    def test_raises_on_missing_block(self) -> None:
        with pytest.raises(AgentParseError, match="No.*json.*block"):
            ClaudeCodeAgent._parse_json_block("No JSON here", stage="test")

    def test_raises_on_invalid_json(self) -> None:
        output = "```json\n{invalid json}\n```"
        with pytest.raises(AgentParseError, match="Invalid JSON"):
            ClaudeCodeAgent._parse_json_block(output, stage="test")

    def test_extracts_first_block_when_multiple(self) -> None:
        output = '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```'
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"first": 1}

    def test_handles_whitespace_around_json(self) -> None:
        output = "```json\n\n  {\"key\": \"value\"}  \n\n```"
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# _run_claude
# ---------------------------------------------------------------------------


class TestRunClaude:
    @pytest.mark.asyncio
    async def test_returns_stdout_lines(self) -> None:
        """_run_claude should return joined stdout lines."""
        agent = ClaudeCodeAgent(timeout=10)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _make_async_iter(["line1\n", "line2\n"])
        mock_proc.stderr = _make_readable(b"")
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await agent._run_claude("test prompt")

        assert "line1" in result
        assert "line2" in result

    @pytest.mark.asyncio
    async def test_calls_notify_log_for_each_line(self) -> None:
        """Each stdout line should trigger notify_log callback."""
        agent = ClaudeCodeAgent(timeout=10)
        logged_lines: list[str] = []

        async def capture_log(line: str) -> None:
            logged_lines.append(line)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _make_async_iter(["hello\n", "world\n"])
        mock_proc.stderr = _make_readable(b"")
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await agent._run_claude("prompt", notify_log=capture_log)

        assert "hello" in logged_lines
        assert "world" in logged_lines

    @pytest.mark.asyncio
    async def test_raises_agent_error_on_nonzero_exit(self) -> None:
        """Non-zero exit code should raise AgentError."""
        agent = ClaudeCodeAgent(timeout=10)

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = _make_async_iter([])
        mock_proc.stderr = _make_readable(b"some error")
        mock_proc.wait = AsyncMock(return_value=1)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            with pytest.raises(AgentError, match="exited with code 1"):
                await agent._run_claude("prompt")

    @pytest.mark.asyncio
    async def test_raises_agent_error_when_binary_not_found(self