"""Unit tests for stage result dataclasses."""

from app.services.stage_results import (
    BrainstormResult,
    ImplementResult,
    Plan,
    TestResult,
    VerificationResult,
)


def test_brainstorm_result_to_dict() -> None:
    result = BrainstormResult(
        analysis="用户需要一个登录页面",
        acceptance_criteria=["能输入用户名密码", "密码错误有提示"],
        key_points=["使用表单验证"],
        estimated_risk="低",
    )
    data = result.to_dict()
    assert data["analysis"] == "用户需要一个登录页面"
    assert len(data["acceptance_criteria"]) == 2
    assert data["estimated_risk"] == "低"


def test_brainstorm_result_defaults() -> None:
    result = BrainstormResult(analysis="简析", acceptance_criteria=["AC1"])
    assert result.key_points == []
    assert result.estimated_risk == ""


def test_plan_to_dict() -> None:
    result = Plan(
        tasks=[
            {"title": "创建登录表单", "file_patterns": ["src/**/Login.tsx"]},
            {"title": "调用 API", "file_patterns": ["src/api/**"]},
        ],
        estimated_risk="中",
        raw_output="[stub output]",
    )
    data = result.to_dict()
    assert len(data["tasks"]) == 2
    assert data["tasks"][0]["title"] == "创建登录表单"


def test_implement_result_to_dict() -> None:
    result = ImplementResult(
        files_changed=["src/Login.tsx", "src/api/auth.ts"],
        summary="实现了登录功能",
        commit_hash="abc123",
    )
    data = result.to_dict()
    assert data["files_changed"] == ["src/Login.tsx", "src/api/auth.ts"]
    assert data["commit_hash"] == "abc123"


def test_test_result_passed() -> None:
    result = TestResult(passed=True, report="2 passed in 1.5s", passed_count=2, failed_count=0)
    data = result.to_dict()
    assert data["passed"] is True
    assert data["failed_count"] == 0


def test_test_result_failed() -> None:
    result = TestResult(passed=False, report="1 passed, 2 failed", passed_count=1, failed_count=2)
    data = result.to_dict()
    assert data["passed"] is False
    assert data["failed_count"] == 2


def test_verification_result_success() -> None:
    result = VerificationResult(
        passed=True, test_passed=True,
        merge_url="https://github.com/org/repo/pull/5", conflicts=[],
    )
    data = result.to_dict()
    assert data["passed"] is True
    assert data["merge_url"] == "https://github.com/org/repo/pull/5"


def test_verification_result_conflict() -> None:
    result = VerificationResult(
        passed=False, test_passed=True,
        conflicts=["src/auth.ts", "src/config.ts"],
        error_message="Rebase conflict in 2 files",
    )
    data = result.to_dict()
    assert data["passed"] is False
    assert "src/auth.ts" in data["conflicts"]
    assert data["merge_url"] is None
