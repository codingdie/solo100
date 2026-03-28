"""BaseAgent abstract interface."""

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from app.models.feature import Feature
from app.services.stage_results import BrainstormResult, ImplementResult, Plan

LogCallback = Callable[[str], Awaitable[None]]


class BaseAgent(ABC):
    """Abstract base class for all AI Agent implementations."""

    @abstractmethod
    async def brainstorm(
        self,
        feature: Feature,
        previous: BrainstormResult | None = None,
        failure_reason: str | None = None,
        notify_log: LogCallback | None = None,
    ) -> BrainstormResult: ...

    @abstractmethod
    async def plan(
        self,
        feature: Feature,
        brainstorm: BrainstormResult,
        previous_plan: Plan | None = None,
        notify_log: LogCallback | None = None,
    ) -> Plan: ...

    @abstractmethod
    async def implement(
        self,
        feature: Feature,
        plan: Plan,
        worktree_path: str,
        notify_log: LogCallback | None = None,
    ) -> ImplementResult: ...
