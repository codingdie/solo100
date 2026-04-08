"""Integration tests for Projects API — real HTTP + real DB."""


class TestProjectsAPI:
    def test_create_project(self, sync_client, db_session):
        payload = {
            "name": "test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        }
        response = sync_client.post("/api/v1/projects", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == "test-project"

    def test_list_projects(self, sync_client, db_session):
        sync_client.post("/api/v1/projects", json={
            "name": "list-test-project",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        response = sync_client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        items = data["items"] if isinstance(data, dict) else data
        assert any(p["name"] == "list-test-project" for p in items)

    def test_get_project(self, sync_client, db_session):
        create_resp = sync_client.post("/api/v1/projects", json={
            "name": "get-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["id"] == project_id

    def test_delete_project(self, sync_client, db_session):
        create_resp = sync_client.post("/api/v1/projects", json={
            "name": "delete-test",
            "ssh_url": "file:///tmp/solo100-test-remote.git",
            "default_branch": "main",
            "ssh_key_env": "TEST_SSH_KEY",
        })
        project_id = create_resp.json()["id"]
        response = sync_client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 204
        assert sync_client.get(f"/api/v1/projects/{project_id}").status_code == 404
