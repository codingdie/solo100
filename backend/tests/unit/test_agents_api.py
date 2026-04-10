"""Tests for AgentConfig CRUD API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_agents_empty(client: AsyncClient) -> None:
    """GET /api/v1/agents returns empty list initially."""
    resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_agent(client: AsyncClient) -> None:
    """POST /api/v1/agents creates an agent config."""
    resp = await client.post("/api/v1/agents", json={
        "name": "claude-test",
        "type": "claude_code",
        "api_key_env": "ANTHROPIC_API_KEY",
        "is_default": False,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "claude-test"
    assert data["type"] == "claude_code"
    assert data["api_key_env"] == "ANTHROPIC_API_KEY"
    assert data["is_default"] is False
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_agent_default_clears_others(client: AsyncClient) -> None:
    """Creating a default agent clears is_default on existing agents."""
    resp1 = await client.post("/api/v1/agents", json={
        "name": "agent-1",
        "api_key_env": "KEY_1",
        "is_default": True,
    })
    agent1_id = resp1.json()["id"]

    resp2 = await client.post("/api/v1/agents", json={
        "name": "agent-2",
        "api_key_env": "KEY_2",
        "is_default": True,
    })
    assert resp2.status_code == 201
    assert resp2.json()["is_default"] is True

    # agent-1 should no longer be default
    list_resp = await client.get("/api/v1/agents")
    agents = {a["id"]: a for a in list_resp.json()["items"]}
    assert agents[agent1_id]["is_default"] is False


@pytest.mark.asyncio
async def test_update_agent(client: AsyncClient) -> None:
    """PUT /api/v1/agents/{id} updates fields partially."""
    create_resp = await client.post("/api/v1/agents", json={
        "name": "before",
        "api_key_env": "KEY_BEFORE",
    })
    agent_id = create_resp.json()["id"]

    resp = await client.put(f"/api/v1/agents/{agent_id}", json={
        "name": "after",
    })
    assert resp.status_code == 200
    assert resp.json()["name"] == "after"
    assert resp.json()["api_key_env"] == "KEY_BEFORE"


@pytest.mark.asyncio
async def test_update_agent_not_found(client: AsyncClient) -> None:
    """PUT /api/v1/agents/{id} returns 404 for non-existent id."""
    resp = await client.put("/api/v1/agents/nonexistent", json={
        "name": "nope",
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(client: AsyncClient) -> None:
    """DELETE /api/v1/agents/{id} removes the agent."""
    create_resp = await client.post("/api/v1/agents", json={
        "name": "to-delete",
        "api_key_env": "KEY_DEL",
    })
    agent_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/v1/agents/{agent_id}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/agents/{agent_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_not_found(client: AsyncClient) -> None:
    """DELETE /api/v1/agents/{id} returns 404 for non-existent id."""
    resp = await client.delete("/api/v1/agents/nonexistent")
    assert resp.status_code == 404
