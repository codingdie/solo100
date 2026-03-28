"""Review Engine — real implementation using Anthropic API.

Replaces ReviewEngineStub from Plan 2.
"""

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict, dataclass

import httpx

from app.models.feature import Feature
from app.services.git_manager import IGitManager

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

_REVIEW_PROMPT = """\
You are a senior software engineer performing a code review.

## Feature
Title: {title}
Description:
{description}

## Git Diff
```diff
{diff}
```

Review the diff above. Identify:
1. Bugs or logic errors
2. Security issues
3. Code quality issues
4. Missing tests

Respond with ONLY a JSON code block:

```json
{{
  "summary": "<overall assessment in 2-3 sentences>",
  "issues": [
    {{
      "severity": "critical|warning|info",
      "file": "<file path>",
      "line": <line number or null>,
      "description": "<issue description>"
    }}
  ]
}}
```
"""


@dataclass
class ReviewIssue:
    severity: str
    file: str
    line: int | None
    description: str


@dataclass
class ReviewReportResult:
    summary: str
    issues: list[ReviewIssue]
    ai_raw: str


class ReviewEngineError(Exception):
    pass


class ReviewEngine:
    """Real Review Engine using Anthropic API."""

    def __init__(self, api_key: str | None = None, api_key_env: str = "ANTHROPIC_API_KEY") -> None:
        self._api_key = api_key or os.environ.get(api_key_env, "")
        self._api_key_env = api_key_env

    async def review(self, feature: Feature, git_manager: IGitManager) -> ReviewReportResult:
        diff = await self._get_diff(feature)

        if not diff.strip():
            logger.warning("ReviewEngine: no diff found for feature %s", feature.id)
            return ReviewReportResult(
                summary="No diff available — skipping AI review.",
                issues=[],
                ai_raw="",
            )

        prompt = _REVIEW_PROMPT.format(
            title=feature.title,
            description=feature.description,
            diff=diff[:8000],  # truncate very large diffs
        )

        raw = await self._call_api(prompt)
        data = self._parse_json_block(raw)

        issues = [
            ReviewIssue(
                severity=i.get("severity", "info"),
                file=i.get("file", ""),
                line=i.get("line"),
                description=i.get("description", ""),
            )
            for i in data.get("issues", [])
        ]

        return ReviewReportResult(
            summary=data.get("summary", ""),
            issues=issues,
            ai_raw=raw,
        )

    async def _get_diff(self, feature: Feature) -> str:
        """Get git diff for the feature branch vs main."""
        worktree = getattr(feature, "worktree_path", None)
        if not worktree:
            return ""

        proc = await asyncio.create_subprocess_exec(
            "git", "diff", "origin/main...HEAD",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=worktree,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode("utf-8", errors="replace")

    async def _call_api(self, prompt: str) -> str:
        api_key = self._api_key or os.environ.get(self._api_key_env, "")
        if not api_key:
            raise ReviewEngineError(f"Anthropic API key not set (env: {self._api_key_env})")

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                ANTHROPIC_API_URL,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

        if resp.status_code != 200:
            raise ReviewEngineError(f"API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        return data["content"][0]["text"]

    @staticmethod
    def _parse_json_block(text: str) -> dict:
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass
        # Fallback: try parsing the whole text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"summary": text[:500], "issues": []}


class ReviewEngineStub:
    """Stub for use in tests."""

    async def review(self, feature: Feature, git_manager: IGitManager) -> ReviewReportResult:
        return ReviewReportResult(
            summary="[STUB] No actual code review performed.",
            issues=[],
            ai_raw="stub",
        )
