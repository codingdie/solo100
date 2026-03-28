"""Unit tests for ReviewEngine."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.review_engine import ReviewEngine, ReviewEngineError


class FakeFeature:
    id = "feat-001"
    title = "Add login"
    description = "OAuth2 login flow"
    worktree_path = "/tmp/worktree"
    branch = "feat/login"


class FakeGitManager:
    async def rebase(self, *a, **kw):
        pass

    async def cleanup_worktree(self, *a, **kw):
        pass


class TestReviewEngine:
    @pytest.mark.asyncio
    async def test_returns_review_report_result(self) -> None:
        engine = ReviewEngine(api_key="test-key")
        response_body = {
            "content": [{"type": "text", "text": json.dumps({
                "summary": "Code looks good overall",
                "issues": [
                    {"severity": "warning", "file": "src/auth.py", "line": 42, "description": "Missing input validation"}
                ]
            })}]
        }

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = response_body
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with patch.object(engine, "_get_diff", new_callable=AsyncMock, return_value="diff --git a/src/auth.py"):
                result = await engine.review(FakeFeature(), FakeGitManager())  # type: ignore[arg-type]

        assert result.summary == "Code looks good overall"
        assert len(result.issues) == 1
        assert result.issues[0].severity == "warning"
        assert result.issues[0].file == "src/auth.py"

    @pytest.mark.asyncio
    async def test_raises_on_api_error(self) -> None:
        engine = ReviewEngine(api_key="test-key")

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = MagicMock()
            mock_resp.status_code = 401
            mock_resp.text = "Unauthorized"
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            with patch.object(engine, "_get_diff", new_callable=AsyncMock, return_value="diff text"):
                with pytest.raises(ReviewEngineError, match="API error"):
                    await engine.review(FakeFeature(), FakeGitManager())  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_empty_diff_returns_stub_report(self) -> None:
        """When there's no diff, return a stub report without calling the API."""
        engine = ReviewEngine(api_key="test-key")

        with patch.object(engine, "_get_diff", new_callable=AsyncMock, return_value=""):
            result = await engine.review(FakeFeature(), FakeGitManager())  # type: ignore[arg-type]

        assert "no diff" in result.summary.lower() or result.summary != ""
        assert result.issues == []
