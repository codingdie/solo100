"""Tests for Project CRUD API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_projects_empty(client: AsyncClient) -> None:
    """GET /api/v1/projects returns empty list initially."""
    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient) -> None:
    """POST /api/v1/projects creates a project and returns 201."""
    payload = {
        "name": "test-project",
        "ssh_url": "git@github.com:test/repo.git",
        "default_branch": "main",
        "ssh_key_env": "SSH_KEY_TEST",
    }
    resp = await client.post("/api/v1/projects", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-project"
    assert data["ssh_url"] == "git@github.com:test/repo.git"
    assert data["default_branch"] == "main"
    assert data["ssh_key_env"] == "SSH_KEY_TEST"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id} returns the created project."""
    payload = {
        "name": "get-test",
        "ssh_url": "git@github.com:test/get.git",
        "ssh_key_env": "SSH_KEY_GET",
    }
    create_resp = await client.post("/api/v1/projects", json=payload)
    project_id = create_resp.json()["id"]

    resp = await client.get(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "get-test"


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient) -> None:
    """GET /api/v1/projects/{id} returns 404 for non-existent id."""
    resp = await client.get("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient) -> None:
    """PUT /api/v1/projects/{id} updates fields partially."""
    payload = {
        "name": "before-update",
        "ssh_url": "git@github.com:test/update.git",
        "ssh_key_env": "SSH_KEY_UP",
    }
    create_resp = await client.post("/api/v1/projects", json=payload)
    project_id = create_resp.json()["id"]

    resp = await client.put(
        f"/api/v1/projects/{project_id}",
        json={"name": "after-update"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "after-update"
    assert resp.json()["ssh_url"] == "git@github.com:test/update.git"


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient) -> None:
    """PUT /api/v1/projects/{id} returns 404 for non-existent id."""
    resp = await client.put(
        "/api/v1/projects/nonexistent-id",
        json={"name": "nope"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project(client: AsyncClient) -> None:
    """DELETE /api/v1/projects/{id} removes the project."""
    payload = {
        "name": "to-delete",
        "ssh_url": "git@github.com:test/delete.git",
        "ssh_key_env": "SSH_KEY_DEL",
    }
    create_resp = await client.post("/api/v1/projects", json=payload)
    project_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/projects/{project_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/projects/{project_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_not_found(client: AsyncClient) -> None:
    """DELETE /api/v1/projects/{id} returns 404 for non-existent id."""
    resp = await client.delete("/api/v1/projects/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_projects_after_create(client: AsyncClient) -> None:
    """GET /api/v1/projects returns created projects."""
    for i in range(3):
        await client.post("/api/v1/projects", json={
            "name": f"proj-{i}",
            "ssh_url": f"git@github.com:test/proj-{i}.git",
            "ssh_key_env": f"SSH_KEY_{i}",
        })

    resp = await client.get("/api/v1/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
