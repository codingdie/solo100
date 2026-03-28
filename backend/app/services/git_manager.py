"""Git Manager — real implementation using subprocess git commands.

Replaces GitManagerStub from Plan 2.
SSH keys are written to temp files, used, then deleted.
"""

import asyncio
import logging
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass
class CloneResult:
    repo_path: str


@dataclass
class BranchResult:
    branch_name: str


@dataclass
class WorktreeResult:
    worktree_path: str


@dataclass
class CommitResult:
    commit_hash: str


@dataclass
class RebaseResult:
    success: bool
    conflicts: list[str]


@dataclass
class PRResult:
    pr_url: str


@dataclass
class MergeResult:
    success: bool


class GitManagerError(Exception):
    pass


@runtime_checkable
class IGitManager(Protocol):
    async def clone(self, ssh_url: str, target_dir: str, ssh_key_env: str) -> CloneResult: ...
    async def create_branch(self, repo_path: str, branch_name: str) -> BranchResult: ...
    async def create_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> WorktreeResult: ...
    async def commit(self, worktree_path: str, message: str, files: list[str]) -> CommitResult: ...
    async def create_pr(self, branch: str, title: str, body: str, repo_url: str) -> PRResult: ...
    async def rebase(self, worktree_path: str, base_branch: str) -> RebaseResult: ...
    async def merge_pr(self, pr_url: str) -> MergeResult: ...
    async def cleanup_worktree(self, worktree_path: str) -> None: ...


async def _run_git(*args: str, cwd: str | None = None, env: dict | None = None) -> tuple[int, str, str]:
    """Run a git command, return (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")


class GitManager(IGitManager):
    """Real Git Manager using subprocess git commands."""

    async def clone(self, ssh_url: str, target_dir: str, ssh_key_env: str) -> CloneResult:
        key_content = os.environ.get(ssh_key_env)
        if not key_content:
            raise GitManagerError(f"SSH key env var '{ssh_key_env}' is not set or empty")

        key_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".key", delete=False, prefix="solo100_ssh_"
        )
        try:
            key_file.write(key_content)
            key_file.flush()
            key_file.close()
            os.chmod(key_file.name, stat.S_IRUSR | stat.S_IWUSR)

            env = {**os.environ, "GIT_SSH_COMMAND": f"ssh -i {key_file.name} -o StrictHostKeyChecking=no"}
            repo_name = ssh_url.rstrip("/").split("/")[-1].removesuffix(".git")
            repo_path = str(Path(target_dir) / repo_name)

            rc, _, stderr = await _run_git("clone", ssh_url, repo_path, env=env)
            if rc != 0:
                raise GitManagerError(f"git clone failed: {stderr}")

            return CloneResult(repo_path=repo_path)
        finally:
            try:
                os.unlink(key_file.name)
            except OSError:
                pass

    async def create_branch(self, repo_path: str, branch_name: str) -> BranchResult:
        rc, _, stderr = await _run_git("checkout", "-b", branch_name, cwd=repo_path)
        if rc != 0:
            raise GitManagerError(f"git checkout -b failed: {stderr}")
        return BranchResult(branch_name=branch_name)

    async def create_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> WorktreeResult:
        rc, _, stderr = await _run_git(
            "worktree", "add", worktree_path, branch_name, cwd=repo_path
        )
        if rc != 0:
            raise GitManagerError(f"git worktree add failed: {stderr}")
        return WorktreeResult(worktree_path=worktree_path)

    async def commit(self, worktree_path: str, message: str, files: list[str]) -> CommitResult:
        # Stage files
        rc, _, stderr = await _run_git("add", *files, cwd=worktree_path)
        if rc != 0:
            raise GitManagerError(f"git add failed: {stderr}")

        # Commit
        rc, _, stderr = await _run_git("commit", "-m", message, cwd=worktree_path)
        if rc != 0:
            raise GitManagerError(f"git commit failed: {stderr}")

        # Get commit hash
        rc, stdout, stderr = await _run_git("rev-parse", "HEAD", cwd=worktree_path)
        if rc != 0:
            raise GitManagerError(f"git rev-parse failed: {stderr}")

        return CommitResult(commit_hash=stdout.strip())

    async def create_pr(self, branch: str, title: str, body: str, repo_url: str) -> PRResult:
        # v0.1: stub — real GitHub API integration in future plan
        logger.warning("GitManager.create_pr: stub implementation, returning placeholder PR URL")
        return PRResult(pr_url=f"{repo_url}/pull/stub")

    async def rebase(self, worktree_path: str, base_branch: str) -> RebaseResult:
        rc, stdout, _ = await _run_git(
            "rebase", f"origin/{base_branch}", cwd=worktree_path
        )
        if rc == 0:
            return RebaseResult(success=True, conflicts=[])

        # Extract conflict file names from output
        conflicts = re.findall(r"CONFLICT \([^)]+\): .*? in (.+)", stdout)
        return RebaseResult(success=False, conflicts=conflicts)

    async def merge_pr(self, pr_url: str) -> MergeResult:
        # v0.1: stub — real GitHub API integration in future plan
        logger.warning("GitManager.merge_pr: stub implementation")
        return MergeResult(success=True)

    async def cleanup_worktree(self, worktree_path: str) -> None:
        rc, _, stderr = await _run_git(
            "worktree", "remove", "--force", worktree_path
        )
        if rc != 0:
            logger.warning("git worktree remove failed: %s", stderr)


class GitManagerStub(IGitManager):
    """Stub for use in tests without real git."""

    async def clone(self, ssh_url: str, target_dir: str, ssh_key_env: str) -> CloneResult:
        return CloneResult(repo_path=f"{target_dir}/cloned_repo")

    async def create_branch(self, repo_path: str, branch_name: str) -> BranchResult:
        return BranchResult(branch_name=branch_name)

    async def create_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> WorktreeResult:
        return WorktreeResult(worktree_path=worktree_path)

    async def commit(self, worktree_path: str, message: str, files: list[str]) -> CommitResult:
        return CommitResult(commit_hash="stub_commit_hash")

    async def create_pr(self, branch: str, title: str, body: str, repo_url: str) -> PRResult:
        return PRResult(pr_url="https://github.com/stub/pr/1")

    async def rebase(self, worktree_path: str, base_branch: str) -> RebaseResult:
        return RebaseResult(success=True, conflicts=[])

    async def merge_pr(self, pr_url: str) -> MergeResult:
        return MergeResult(success=True)

    async def cleanup_worktree(self, worktree_path: str) -> None:
        pass


# Default singleton — real implementation
git_manager: IGitManager = GitManager()
