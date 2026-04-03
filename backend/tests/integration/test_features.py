"""Integration tests for Features API — real HTTP + real DB."""

import pytest


def _create_project(client):
    """Helper: 创建测试用项目，返回 project_id。"""
    resp = client.post("/api/projects", json={
        "name": "feature-test-project",
        "ssh_url": "file:///tmp/solo100-test-remote.git",
        "default_branch": "main",
        "ssh_key_env": "TEST_SSH_KEY",
    })
    return resp.json()["id"]


class TestFeaturesAPI:
    """测试 /api/features 端点。"""

    def test_create_feature(self, sync_client, db_session):
        """POST /api/features 返回 201，状态为 pending。"""
        project_id = _create_project(sync_client)
        payload = {
            "project_id": project_id,
            "title": "测试 Feature",
            "description": "这是一个集成测试 Feature",
        }
        response = sync_client.post("/api/features", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["title"] == "测试 Feature"
        assert data["project_id"] == project_id

    def test_list_features_by_project(self, sync_client, db_session):
        """GET /api/features?project_id=xxx 返回该项目的所有 Feature。"""
        project_id = _create_project(sync_client)
        # 创建两个 feature
        for i in range(2):
            sync_client.post("/api/features", json={
                "project_id": project_id,
                "title": f"Feature {i}",
                "description": f"描述 {i}",
            })
        response = sync_client.get(f"/api/features?project_id={project_id}")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_get_feature(self, sync_client, db_session):
        """GET /api/features/{id} 返回 Feature 详情。"""
        project_id = _create_project(sync_client)
        create_resp = sync_client.post("/api/features", json={
            "project_id": project_id,
            "title": "get-feature-test",
            "description": "测试 GET",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/features/{feature_id}")
        assert response.status_code == 200
        assert response.json()["id"] == feature_id

    def test_update_feature_status(self, sync_client, db_session):
        """PATCH /api/features/{id} 可更新 status 等字段。"""
        project_id = _create_project(sync_client)
        create_resp = sync_client.post("/api/features", json={
            "project_id": project_id,
            "title": "patch-test",
            "description": "测试 PATCH",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.patch(
            f"/api/features/{feature_id}",
            json={"status": "archived"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "archived"
