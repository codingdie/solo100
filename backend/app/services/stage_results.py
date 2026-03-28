"""Structured result types produced by each stage of the Feature pipeline.

These dataclasses are serialized to JSON and stored in FeatureExecution.result_json.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BrainstormResult:
    analysis: str
    acceptance_criteria: list[str]
    key_points: list[str] = field(default_factory=list)
    estimated_risk: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Plan:
    tasks: list[dict[str, Any]]
    estimated_risk: str = ""
    raw_output: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ImplementResult:
    files_changed: list[str]
    summary: str
    commit_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TestResult:
    passed: bool
    report: str
    passed_count: int = 0
    failed_count: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerificationResult:
    passed: bool
    conflicts: list[str] = field(default_factory=list)
    test_passed: bool = False
    merge_url: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
