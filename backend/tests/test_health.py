"""Tests for the meta and health endpoints."""

from httpx import AsyncClient


async def test_root(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "RoboSense"
    assert body["docs"] == "/docs"


async def test_health(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_health_db(client: AsyncClient) -> None:
    """Requires a reachable database (provided by the CI service / docker compose)."""
    resp = await client.get("/api/health/db")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
