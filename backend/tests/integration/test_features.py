"""Integration tests for Features API — real HTTP + real DB."""


def _create_project(client):
    resp = client.post("/api/v1/projects", json={
        "name": "feature-test-project",
        "ssh_url": "file:///tmp/solo100-test-remote.git",
        "default_branch": "main",
        "ssh_key_env": "TEST_SSH_KEY",
    })
    return resp.json()["id"]


class TestFeaturesAPI:
    def test_create_feature(self, sync_client, db_session):
        project_id = _create_project(sync_client)
        response = sync_client.post(f"/api/v1/projects/{project_id}/features", json={
            "title": "测试 Feature",
            "description": "这是一个集成测试 Feature",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["title"] == "测试 Feature"

    def test_list_features_by_project(self, sync_client, db_session):
        project_id = _create_project(sync_client)
        for i in range(2):
            sync_client.post(f"/api/v1/projects/{project_id}/features", json={
                "title": f"Feature {i}",
                "description": f"描述 {i}",
            })
        response = sync_client.get(f"/api/v1/projects/{project_id}/features")
        assert response.status_code == 200
        data = response.json()
        items = data["items"] if isinstance(data, dict) else data
        assert len(items) == 2

    def test_get_feature(self, sync_client, db_session):
        project_id = _create_project(sync_client)
        create_resp = sync_client.post(f"/api/v1/projects/{project_id}/features", json={
            "title": "get-feature-test",
            "description": "测试 GET",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.get(f"/api/v1/features/{feature_id}")
        assert response.status_code == 200
        assert response.json()["id"] == feature_id

    def test_archive_feature(self, sync_client, db_session):
        project_id = _create_project(sync_client)
        create_resp = sync_client.post(f"/api/v1/projects/{project_id}/features", json={
            "title": "archive-test",
            "description": "测试 archive",
        })
        feature_id = create_resp.json()["id"]
        response = sync_client.post(f"/api/v1/features/{feature_id}/archive")
        assert response.status_code == 200
        assert response.json()["status"] == "archived"
