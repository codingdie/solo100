"""Unit tests for BaseAgent interface contract."""

import pytest

from app.agents.base import BaseAgent, LogCallback
from app.services.stage_results import BrainstormResult, ImplementResult, Plan


class ConcreteAgent(BaseAgent):
    async def brainstorm(self, feature, previous=None, failure_reason=None, notify_log=None):
        return BrainstormResult(analysis="test analysis", acceptance_criteria=["AC1"])

    async def plan(self, feature, brainstorm, previous_plan=None, notify_log=None):
        return Plan(tasks=[{"title": "task1", "file_patterns": [], "description": "d"}])

    async def implement(self, feature, plan, worktree_path, notify_log=None):
        return ImplementResult(files_changed=[], summary="done")


class FakeFeature:
    id = "feat-001"
    title = "Test Feature"
    description = "Test description"


def test_base_agent_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseAgent()  # type: ignore[abstract]


def test_concrete_agent_instantiates() -> None:
    assert isinstance(ConcreteAgent(), BaseAgent)


@pytest.mark.asyncio
async def test_brainstorm_returns_result() -> None:
    result = await ConcreteAgent().brainstorm(FakeFeature())  # type: ignore[arg-type]
    assert isinstance(result, BrainstormResult)
    assert result.analysis == "test analysis"


@pytest.mark.asyncio
async def test_plan_returns_plan() -> None:
    brainstorm = BrainstormResult(analysis="a", acceptance_criteria=["AC1"])
    result = await ConcreteAgent().plan(FakeFeature(), brainstorm)  # type: ignore[arg-type]
    assert isinstance(result, Plan)
    assert len(result.tasks) == 1


@pytest.mark.asyncio
async def test_notify_log_is_optional() -> None:
    result = await ConcreteAgent().brainstorm(FakeFeature(), notify_log=None)  # type: ignore[arg-type]
    assert result is not None
