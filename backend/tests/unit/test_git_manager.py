"""Unit tests for real GitManager."""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.git_manager import GitManager, GitManagerError


class TestGitManagerClone:
    @pytest.mark.asyncio
    async def test_clone_calls_git_with_ssh_env(self) -> None:
        """clone() must set GIT_SSH_COMMAND with the key file."""
        manager = GitManager()
        with tempfile.TemporaryDirectory() as tmpdir:
            key_env = "TEST_SSH_KEY"
            fake_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nfake\n-----END OPENSSH PRIVATE KEY-----"
            with patch.dict(os.environ, {key_env: fake_key}):
                with patch("asyncio.create_subprocess_exec") as mock_exec:
                    mock_proc = MagicMock()
                    mock_proc.returncode = 0
                    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
                    mock_exec.return_value = mock_proc

                    result = await manager.clone(
                        ssh_url="git@github.com:test/repo.git",
                        target_dir=tmpdir,
                        ssh_key_env=key_env,
                    )

        assert result.repo_path == str(Path(tmpdir) / "repo")
        call_args = mock_exec.call_args
        env = call_args.kwargs.get("env") or {}
        assert "GIT_SSH_COMMAND" in env
        assert "ssh -i" in env["GIT_SSH_COMMAND"]

    @pytest.mark.asyncio
    async def test_clone_raises_on_missing_key_env(self) -> None:
        """clone() raises GitManagerError if the SSH key env var is not set."""
        manager = GitManager()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(GitManagerError, match="SSH key env var"):
                await manager.clone(
                    ssh_url="git@github.com:test/repo.git",
                    target_dir="/tmp/test",
                    ssh_key_env="MISSING_KEY_ENV",
                )


class TestGitManagerCreateBranch:
    @pytest.mark.asyncio
    async def test_create_branch_runs_git_checkout(self) -> None:
        manager = GitManager()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_proc

            result = await manager.create_branch(
                repo_path="/tmp/repo", branch_name="feat/test-branch"
            )

        assert result.branch_name == "feat/test-branch"
        args = mock_exec.call_args[0]
        assert "checkout" in args or "branch" in args


class TestGitManagerCommit:
    @pytest.mark.asyncio
    async def test_commit_returns_hash(self) -> None:
        manager = GitManager()
        commit_hash = "abc123def456"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(
                side_effect=[
                    (b"", b""),           # git add
                    (b"", b""),           # git commit
                    (commit_hash.encode(), b""),  # git rev-parse HEAD
                ]
            )
            mock_exec.return_value = mock_proc

            result = await manager.commit(
                worktree_path="/tmp/worktree",
                message="feat: add login",
                files=["src/auth.py"],
            )

        assert result.commit_hash == commit_hash


class TestGitManagerRebase:
    @pytest.mark.asyncio
    async def test_rebase_success(self) -> None:
        manager = GitManager()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_proc

            result = await manager.rebase(
                worktree_path="/tmp/worktree", base_branch="main"
            )

        assert result.success is True
        assert result.conflicts == []

    @pytest.mark.asyncio
    async def test_rebase_conflict_returns_conflict_files(self) -> None:
        manager = GitManager()
        conflict_output = b"CONFLICT (content): Merge conflict in src/auth.py\nCONFLICT (content): Merge conflict in src/config.py\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 1
            mock_proc.communicate = AsyncMock(return_value=(conflict_output, b""))
            mock_exec.return_value = mock_proc

            result = await manager.rebase(
                worktree_path="/tmp/worktree", base_branch="main"
            )

        assert result.success is False
        assert "src/auth.py" in result.conflicts
        assert "src/config.py" in result.conflicts


class TestGitManagerCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_worktree_runs_git_worktree_remove(self) -> None:
        manager = GitManager()
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_proc

            await manager.cleanup_worktree("/tmp/worktree")

        args = mock_exec.call_args[0]
        assert "worktree" in args
        assert "remove" in args
