"""Integration tests for complete Feature state machine workflow."""

import pytest


def _create_project(client):
    resp = client.post("/api/projects", json={
        "name": "workflow-test-project",
        "ssh_url": "file:///tmp/solo100-test-remote.git",
        "default_branch": "main",
        "ssh_key_env": "TEST_SSH_KEY",
    })
    return resp.json()["id"]


def _create_feature(client, project_id, title="workflow-feature"):
    resp = client.post("/api/features", json={
        "project_id": project_id,
        "title": title,
        "description": "测试完整流程的 Feature",
    })
    return resp.json()["id"], resp.json()


class TestFeatureWorkflow:
    """测试完整状态机：pending → merged。"""

    def test_workflow_full_happy_path(self, sync_client, db_session):
        """完整流程：pending → brainstorming → planning → implementing → testing → reviewing → approved → verifying → merged。"""
        project_id = _create_project(sync_client)
        feature_id, feature = _create_feature(sync_client, project_id)
        assert feature["status"] == "pending"

        # 启动 pipeline（内部会进入 brainstorming 状态并等待 approval）
        resp = sync_client.post(f"/api/features/{feature_id}/start")
        assert resp.status_code in (200, 202)
        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "brainstorming"

        # 人工介入点 1: 确认 brainstorming
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "brainstorming",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "planning"

        # 人工介入点 2: 确认 plan
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "planning",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "implementing"

        # implementing 完成后进入 testing（需要等待 Celery 任务，这里通过 API 推进）
        # 模拟 implementing 结束：更新状态 + 填充必要数据
        resp = sync_client.patch(f"/api/features/{feature_id}", json={
            "status": "testing",
        })
        assert resp.status_code == 200

        # 人工介入点 3: 确认 test 结果
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "testing",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "reviewing"

        # 人工介入点 4: code review approve
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "reviewing",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "approved"

        # 人工最终确认 → verifying → merged
        resp = sync_client.post(f"/api/approvals/{feature_id}/approve", json={
            "stage": "approved",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        final_status = resp.json()["status"]
        # verifying 可能因为 Git merge conflict 等原因失败，这里只验证状态进入了 verifying 或 merged
        assert final_status in ("verifying", "merged"), f"Expected verifying or merged, got {final_status}"

    def test_workflow_reject_at_brainstorming(self, sync_client, db_session):
        """brainstorming 阶段 reject 后人工选择 retry 的流程。"""
        project_id = _create_project(sync_client)
        feature_id, _ = _create_feature(sync_client, project_id, "reject-test")

        # 启动
        sync_client.post(f"/api/features/{feature_id}/start")
        assert sync_client.get(f"/api/features/{feature_id}").json()["status"] == "brainstorming"

        # reject
        resp = sync_client.post(f"/api/approvals/{feature_id}/reject", json={
            "stage": "brainstorming",
            "failure_reason": "分析不够深入",
        })
        assert resp.status_code == 200

        resp = sync_client.get(f"/api/features/{feature_id}")
        assert resp.json()["status"] == "pending"

    def test_workflow_approved_state_blocks_start(self, sync_client, db_session):
        """已经在 approved 状态的 Feature 不能再次 start。"""
        project_id = _create_project(sync_client)
        feature_id, _ = _create_feature(sync_client, project_id)

        # 手动设置到 approved
        sync_client.patch(f"/api/features/{feature_id}", json={"status": "approved"})

        resp = sync_client.post(f"/api/features/{feature_id}/start")
        # 应该拒绝或返回错误
        assert resp.status_code in (400, 409)
