"""Tests for health check and root endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """GET /health returns ok status."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    """GET / returns welcome message."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "solo100" in resp.json()["message"]
