"""Mock implementation of BaseAgent for integration tests.

Returns fixed structured results without calling any LLM API.
"""

from app.agents.base import BaseAgent
from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


class MockClaudeCodeAgent(BaseAgent):
    """Returns fixed structured results without calling any LLM API."""

    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log=None,
    ) -> BrainstormResult:
        if failure_reason:
            return BrainstormResult(
                analysis=f"Mock re-analysis after failure: {failure_reason}",
                acceptance_criteria=["验收条件1", "验收条件2"],
                key_points=["关键点1", "关键点2"],
                estimated_risk="low",
            )
        return BrainstormResult(
            analysis="Mock: 分析需求完成",
            acceptance_criteria=["验收条件1", "验收条件2"],
            key_points=["关键点1", "关键点2"],
            estimated_risk="low",
        )

    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log=None,
    ) -> Plan:
        if previous_plan:
            return Plan(
                tasks=[
                    {"title": "修订任务1", "description": "在已有基础上修改", "files": ["a.py"]},
                ],
                estimated_risk="low",
                raw_output="Mock revised plan",
            )
        return Plan(
            tasks=[
                {
                    "title": "任务1：实现基础结构",
                    "description": "创建 a.py 并实现基础结构",
                    "files": ["a.py"],
                },
                {
                    "title": "任务2：实现核心逻辑",
                    "description": "创建 b.py 并实现核心逻辑",
                    "files": ["b.py"],
                },
            ],
            estimated_risk="low",
            raw_output="Mock plan output",
        )

    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log=None,
    ) -> ImplementResult:
        import os

        for task in plan.tasks:
            for file_path in task.get("files", []):
                full_path = os.path.join(worktree_path, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, "w") as f:
                    f.write(f"# Mock implementation for {file_path}\n")
        return ImplementResult(
            files_changed=[f for t in plan.tasks for f in t.get("files", [])],
            summary="Mock: 代码实现完成",
            commit_hash="abc1234",
        )
