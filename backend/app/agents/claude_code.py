"""ClaudeCodeAgent — calls the Claude Code CLI via subprocess."""

import asyncio
import json
import logging
import re
from typing import Any

from app.agents.base import BaseAgent, LogCallback
from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300
_JSON_BLOCK_RE = re.compile(r"```json\s*([\s\S]*?)\s*```", re.MULTILINE)


class AgentError(Exception):
    pass


class AgentTimeoutError(AgentError):
    pass


class AgentParseError(AgentError):
    pass


_BRAINSTORM_PROMPT = """\
You are a senior software engineer performing a feature analysis.

## Feature
Title: {title}
Description:
{description}

{previous_section}

## Task
Analyse this feature. Identify:
1. What needs to be built (technical analysis)
2. Acceptance criteria (concrete, testable conditions)
3. Key implementation points
4. Estimated risk level: low | medium | high

## Output Format
Respond with ONLY a JSON code block:

```json
{{
  "analysis": "<detailed technical analysis>",
  "acceptance_criteria": ["<criterion 1>", "<criterion 2>"],
  "key_points": ["<point 1>", "<point 2>"],
  "estimated_risk": "low|medium|high"
}}
```
"""

_PLAN_PROMPT = """\
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

## Output Format
Respond with ONLY a JSON code block:

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

_IMPLEMENT_PROMPT = """\
You are a senior software engineer implementing a feature.

## Feature
Title: {title}
Description:
{description}

## Implementation Plan
{plan_tasks}

## Working Directory
{worktree_path}

Implement ALL tasks. Work in: {worktree_path}
Do NOT commit — only write the files.

```json
{{
  "files_changed": ["<relative path>"],
  "summary": "<brief description>"
}}
```
"""


class ClaudeCodeAgent(BaseAgent):
    """Agent that calls the Claude Code CLI via subprocess."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, claude_bin: str = "claude") -> None:
        self._timeout = timeout
        self._claude_bin = claude_bin

    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> BrainstormResult:
        previous_section = ""
        if previous is not None:
            previous_section = (
                f"## Previous Analysis\n{previous.analysis}\n\n"
                f"## Failure Reason\n{failure_reason or 'Not specified'}\n\n"
                "Please improve on the previous analysis."
            )
        prompt = _BRAINSTORM_PROMPT.format(
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
        previous_plan_section = ""
        if previous_plan is not None:
            tasks_str = json.dumps(previous_plan.tasks, indent=2, ensure_ascii=False)
            previous_plan_section = f"## Previous Plan (improve on it)\n```json\n{tasks_str}\n```\n"
        prompt = _PLAN_PROMPT.format(
            title=feature.title,
            description=feature.description,
            analysis=brainstorm.analysis,
            acceptance_criteria="\n".join(f"- {c}" for c in brainstorm.acceptance_criteria),
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
        tasks_str = "\n".join(
            f"{i+1}. **{t.get('title','')}**\n"
            f"   Files: {', '.join(t.get('file_patterns',[]))}\n"
            f"   {t.get('description','')}"
            for i, t in enumerate(plan.tasks)
        )
        prompt = _IMPLEMENT_PROMPT.format(
            title=feature.title,
            description=feature.description,
            plan_tasks=tasks_str,
            worktree_path=worktree_path,
        )
        output = await self._run_claude(prompt, cwd=worktree_path, notify_log=notify_log)
        data = self._parse_json_block(output, stage="implement")
        return ImplementResult(
            files_changed=data.get("files_changed", []),
            summary=data.get("summary", ""),
            commit_hash=None,
        )

    async def _run_claude(
        self,
        prompt: str,
        cwd: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> str:
        cmd = [self._claude_bin, "--print", prompt]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except FileNotFoundError as exc:
            raise AgentError(
                f"Claude Code CLI not found: '{self._claude_bin}'. Ensure it is installed and in PATH."
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
                        pass

        try:
            await asyncio.wait_for(_read_stdout(), timeout=self._timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise AgentTimeoutError(f"Claude Code CLI timed out after {self._timeout}s")

        await proc.wait()

        if proc.returncode != 0:
            stderr_text = b""
            if proc.stderr:
                stderr_text = await proc.stderr.read()
            raise AgentError(
                f"Claude Code CLI exited with code {proc.returncode}. "
                f"stderr: {stderr_text.decode('utf-8', errors='replace')[:500]}"
            )

        return "\n".join(lines)

    @staticmethod
    def _parse_json_block(output: str, stage: str) -> dict[str, Any]:
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
                f"Invalid JSON in {stage} output: {exc}. JSON text: {json_text[:300]}"
            ) from exc
