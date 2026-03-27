"""Tests for Feature CRUD and state-transition API endpoints."""

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    """Helper: create a project and return its id."""
    resp = await client.post("/api/v1/projects", json={
        "name": "feat-test-proj",
        "ssh_url": "git@github.com:test/feat.git",
        "ssh_key_env": "SSH_KEY_FEAT",
    })
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_features_empty(client: AsyncClient) -> None:
    """GET /projects/{id}/features returns empty list initially."""
    project_id = await _create_project(client)
    resp = await client.get(f"/api/v1/projects/{project_id}/features")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_features_project_not_found(client: AsyncClient) -> None:
    """GET /projects/{id}/features returns 404 for non-existent project."""
    resp = await client.get("/api/v1/projects/nonexistent/features")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_feature(client: AsyncClient) -> None:
    """POST /projects/{id}/features creates a feature with pending status."""
    project_id = await _create_project(client)
    resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Add login page",
        "description": "Implement OAuth2 login flow",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Add login page"
    assert data["description"] == "Implement OAuth2 login flow"
    assert data["status"] == "pending"
    assert data["project_id"] == project_id
    assert data["retry_count"] == 0
    assert data["max_retries"] == 3
    assert data["branch"] is None
    assert data["pr_url"] is None


@pytest.mark.asyncio
async def test_create_feature_project_not_found(client: AsyncClient) -> None:
    """POST /projects/{id}/features returns 404 for non-existent project."""
    resp = await client.post("/api/v1/projects/nonexistent/features", json={
        "title": "test",
        "description": "test",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_feature(client: AsyncClient) -> None:
    """GET /features/{id} returns the created feature."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Get test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/features/{feature_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get test"


@pytest.mark.asyncio
async def test_get_feature_not_found(client: AsyncClient) -> None:
    """GET /features/{id} returns 404 for non-existent id."""
    resp = await client.get("/api/v1/features/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_start_feature_returns_501(client: AsyncClient) -> None:
    """POST /features/{id}/start returns 501 (not yet implemented)."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Start test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/start")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_archive_feature_returns_501(client: AsyncClient) -> None:
    """POST /features/{id}/archive returns 501 (not yet implemented)."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Archive test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/archive")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_reset_feature_returns_501(client: AsyncClient) -> None:
    """POST /features/{id}/reset returns 501 (not yet implemented)."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Reset test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/reset")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_list_feature_executions_empty(client: AsyncClient) -> None:
    """GET /features/{id}/executions returns empty list initially."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Exec test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/features/{feature_id}/executions")
    assert resp.status_code == 200
    assert resp.json()["items"] == []


@pytest.mark.asyncio
async def test_get_feature_review_none(client: AsyncClient) -> None:
    """GET /features/{id}/review returns null when no review exists."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Review test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/features/{feature_id}/review")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_approve_feature_returns_501(client: AsyncClient) -> None:
    """POST /features/{id}/approve returns 501 (not yet implemented)."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Approve test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/approve")
    assert resp.status_code == 501


@pytest.mark.asyncio
async def test_reject_feature_returns_501(client: AsyncClient) -> None:
    """POST /features/{id}/reject returns 501 (not yet implemented)."""
    project_id = await _create_project(client)
    create_resp = await client.post(f"/api/v1/projects/{project_id}/features", json={
        "title": "Reject test",
        "description": "desc",
    })
    feature_id = create_resp.json()["id"]

    resp = await client.post(f"/api/v1/features/{feature_id}/reject")
    assert resp.status_code == 501
