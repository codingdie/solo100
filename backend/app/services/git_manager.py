"""Git Manager — stub implementation.

Real implementation in Plan 3 (Git Manager).
This stub satisfies the interface for FeatureExecutor without doing real Git ops.
"""

import logging
from dataclasses import dataclass
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


@runtime_checkable
class IGitManager(Protocol):
    """Protocol defining the Git Manager interface expected by FeatureExecutor."""

    async def clone(self, ssh_url: str, target_dir: str, ssh_key_env: str) -> CloneResult: ...
    async def create_branch(self, repo_path: str, branch_name: str) -> BranchResult: ...
    async def create_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> WorktreeResult: ...
    async def commit(self, worktree_path: str, message: str, files: list[str]) -> CommitResult: ...
    async def create_pr(self, branch: str, title: str, body: str, repo_url: str) -> PRResult: ...
    async def rebase(self, worktree_path: str, base_branch: str) -> RebaseResult: ...
    async def merge_pr(self, pr_url: str) -> MergeResult: ...
    async def cleanup_worktree(self, worktree_path: str) -> None: ...


class GitManagerStub(IGitManager):
    """Stub Git Manager that logs operations without performing real Git actions."""

    async def clone(self, ssh_url: str, target_dir: str, ssh_key_env: str) -> CloneResult:
        logger.warning("[GitManagerStub] clone() called — real implementation in Plan 3")
        return CloneResult(repo_path=f"{target_dir}/cloned_repo")

    async def create_branch(self, repo_path: str, branch_name: str) -> BranchResult:
        logger.warning("[GitManagerStub] create_branch() called — real implementation in Plan 3")
        return BranchResult(branch_name=branch_name)

    async def create_worktree(self, repo_path: str, branch_name: str, worktree_path: str) -> WorktreeResult:
        logger.warning("[GitManagerStub] create_worktree() called — real implementation in Plan 3")
        return WorktreeResult(worktree_path=worktree_path)

    async def commit(self, worktree_path: str, message: str, files: list[str]) -> CommitResult:
        logger.warning("[GitManagerStub] commit() called — real implementation in Plan 3")
        return CommitResult(commit_hash="stub_commit_hash")

    async def create_pr(self, branch: str, title: str, body: str, repo_url: str) -> PRResult:
        logger.warning("[GitManagerStub] create_pr() called — real implementation in Plan 3")
        return PRResult(pr_url="https://github.com/stub/pr/1")

    async def rebase(self, worktree_path: str, base_branch: str) -> RebaseResult:
        logger.warning("[GitManagerStub] rebase() called — real implementation in Plan 3")
        return RebaseResult(success=True, conflicts=[])

    async def merge_pr(self, pr_url: str) -> MergeResult:
        logger.warning("[GitManagerStub] merge_pr() called — real implementation in Plan 3")
        return MergeResult(success=True)

    async def cleanup_worktree(self, worktree_path: str) -> None:
        logger.warning("[GitManagerStub] cleanup_worktree() called — real implementation in Plan 3")


# Singleton instance — replace with real GitManager after Plan 3
git_manager: IGitManager = GitManagerStub()
