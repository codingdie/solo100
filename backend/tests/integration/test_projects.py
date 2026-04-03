"""Integration tests for Projects API — real HTTP + real DB."""

import pytest


class TestProjectsAPI:
    """测试 /api/projects 端点。"""

    def test_create_project(self, sync_client, db_session):
        """POST /api/projects 返回 201 且包含 id 和 name。"""
        payload = {
            "name": "test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        }
        response = sync_client.post("/api/projects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-project"
        assert data["ssh_url"] == payload["ssh_url"]

    def test_list_projects(self, sync_client, db_session):
        """GET /api/projects 返回项目列表。"""
        # 先创建一个项目
        sync_client.post("/api/projects", json={
            "name": "list-test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        response = sync_client.get("/api/projects")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(p["name"] == "list-test-project" for p in data)

    def test_get_project(self, sync_client, db_session):
        """GET /api/projects/{id} 返回单个项目详情。"""
        create_resp = sync_client.post("/api/projects", json={
            "name": "get-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["id"] == project_id

    def test_delete_project(self, sync_client, db_session):
        """DELETE /api/projects/{id} 返回 204。"""
        create_resp = sync_client.post("/api/projects", json={
            "name": "delete-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.delete(f"/api/projects/{project_id}")
        assert response.status_code == 204
        # 再次获取应返回 404
        assert sync_client.get(f"/api/projects/{project_id}").status_code == 404
