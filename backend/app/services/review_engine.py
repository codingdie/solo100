"""Review Engine — stub implementation.

Real implementation in Plan 3 (Review Engine).
This stub returns a dummy review report so the state machine can proceed.
"""

import logging
from dataclasses import asdict, dataclass

from app.models.feature import Feature
from app.services.git_manager import IGitManager

logger = logging.getLogger(__name__)


@dataclass
class ReviewIssue:
    severity: str  # "critical" | "warning" | "info"
    file: str
    line: int | None
    description: str


@dataclass
class ReviewReportResult:
    summary: str
    issues: list[ReviewIssue]
    ai_raw: str


class ReviewEngineStub:
    """Stub Review Engine — generates a dummy report without real AI analysis."""

    async def review(self, feature: Feature, git_manager: IGitManager) -> ReviewReportResult:
        logger.warning("[ReviewEngineStub] review() called — real implementation in Plan 3")
        return ReviewReportResult(
            summary="[STUB] No actual code review performed. Real review in Plan 3.",
            issues=[],
            ai_raw="stub review output",
        )
