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
from app.services.stage_results import BrainstormResult, Plan


class FakeFeature:
    id = "feat-test-001"
    title = "Add user authentication"
    description = "Implement OAuth2 login and logout."


def _make_output(data: dict) -> str:
    return f"Some preamble\n```json\n{json.dumps(data)}\n```\nTrailing text"


def _make_async_iter(lines: list[str]):
    """Create an async iterable from a list of byte strings."""
    async def _gen():
        for line in lines:
            yield line.encode() if isinstance(line, str) else line
    return _gen()


def _make_readable(data: bytes):
    mock = AsyncMock()
    mock.read = AsyncMock(return_value=data)
    return mock


class TestParseJsonBlock:
    def test_extracts_json_block(self) -> None:
        output = 'Some text\n```json\n{"key": "value"}\n```\nMore text'
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"key": "value"}

    def test_raises_on_missing_block(self) -> None:
        with pytest.raises(AgentParseError, match="No.*json.*block"):
            ClaudeCodeAgent._parse_json_block("No JSON here", stage="test")

    def test_raises_on_invalid_json(self) -> None:
        with pytest.raises(AgentParseError, match="Invalid JSON"):
            ClaudeCodeAgent._parse_json_block("```json\n{invalid}\n```", stage="test")

    def test_extracts_first_block_when_multiple(self) -> None:
        output = '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```'
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"first": 1}

    def test_handles_whitespace_around_json(self) -> None:
        output = '```json\n\n  {"key": "value"}  \n\n```'
        result = ClaudeCodeAgent._parse_json_block(output, stage="test")
        assert result == {"key": "value"}


class TestRunClaude:
    @pytest.mark.asyncio
    async def test_returns_stdout_lines(self) -> None:
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
        agent = ClaudeCodeAgent(timeout=10)
        logged: list[str] = []

        async def capture(line: str) -> None:
            logged.append(line)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _make_async_iter(["hello\n", "world\n"])
        mock_proc.stderr = _make_readable(b"")
        mock_proc.wait = AsyncMock(return_value=0)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            await agent._run_claude("prompt", notify_log=capture)

        assert "hello" in logged
        assert "world" in logged

    @pytest.mark.asyncio
    async def test_raises_on_nonzero_exit(self) -> None:
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
    async def test_raises_when_binary_not_found(self) -> None:
        agent = ClaudeCodeAgent(timeout=10, claude_bin="nonexistent-bin")
        with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
            with pytest.raises(AgentError, match="not found"):
                await agent._run_claude("prompt")


class TestBrainstorm:
    @pytest.mark.asyncio
    async def test_returns_brainstorm_result(self) -> None:
        agent = ClaudeCodeAgent(timeout=10)
        output = _make_output({
            "analysis": "Need OAuth2 flow",
            "acceptance_criteria": ["User can login", "User can logout"],
            "key_points": ["Use JWT"],
            "estimated_risk": "medium",
        })

        with patch.object(agent, "_run_claude", new_callable=AsyncMock, return_value=output):
            result = await agent.brainstorm(FakeFeature())  # type: ignore[arg-type]

        assert isinstance(result, BrainstormResult)
        assert result.analysis == "Need OAuth2 flow"
        assert len(result.acceptance_criteria) == 2
        assert result.estimated_risk == "medium"

    @pytest.mark.asyncio
    async def test_includes_previous_in_prompt(self) -> None:
        agent = ClaudeCodeAgent(timeout=10)
        output = _make_output({
            "analysis": "Improved analysis",
            "acceptance_criteria": ["AC1"],
            "key_points": [],
            "estimated_risk": "low",
        })
        previous = BrainstormResult(analysis="old analysis", acceptance_criteria=["old AC"])
        captured_prompt: list[str] = []

        async def mock_run(prompt, **kwargs):
            captured_prompt.append(prompt)
            return output

        with patch.object(agent, "_run_claude", side_effect=mock_run):
            await agent.brainstorm(FakeFeature(), previous=previous, failure_reason="too vague")  # type: ignore[arg-type]

        assert "old analysis" in captured_prompt[0]
        assert "too vague" in captured_prompt[0]


class TestPlan:
    @pytest.mark.asyncio
    async def test_returns_plan(self) -> None:
        agent = ClaudeCodeAgent(timeout=10)
        output = _make_output({
            "tasks": [{"title": "Create login form", "file_patterns": ["src/**"], "description": "..."}],
            "estimated_risk": "low",
        })
        brainstorm = BrainstormResult(analysis="analysis", acceptance_criteria=["AC1"])

        with patch.object(agent, "_run_claude", new_callable=AsyncMock, return_value=output):
            result = await agent.plan(FakeFeature(), brainstorm)  # type: ignore[arg-type]

        assert isinstance(result, Plan)
        assert len(result.tasks) == 1
        assert result.tasks[0]["title"] == "Create login form"


class TestImplement:
    @pytest.mark.asyncio
    async def test_returns_implement_result(self) -> None:
        agent = ClaudeCodeAgent(timeout=10)
        output = _make_output({
            "files_changed": ["src/auth.py", "tests/test_auth.py"],
            "summary": "Implemented OAuth2 login",
        })
        plan = Plan(tasks=[{"title": "t1", "file_patterns": ["src/**"], "description": "d"}])

        with patch.object(agent, "_run_claude", new_callable=AsyncMock, return_value=output):
            result = await agent.implement(FakeFeature(), plan, "/tmp/worktree")  # type: ignore[arg-type]

        assert result.files_changed == ["src/auth.py", "tests/test_auth.py"]
        assert result.summary == "Implemented OAuth2 login"
        assert result.commit_hash is None
