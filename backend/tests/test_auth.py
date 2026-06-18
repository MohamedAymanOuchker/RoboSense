"""Tests for the auth endpoints."""

from httpx import AsyncClient

CREDS = {"email": "alice@example.com", "password": "supersecret123"}


async def test_register_returns_user(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/register", json=CREDS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == CREDS["email"]
    assert "id" in body and "created_at" in body
    assert "password" not in body
    assert "password_hash" not in body


async def test_register_rejects_short_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register", json={"email": "x@example.com", "password": "short"}
    )
    assert resp.status_code == 422


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=CREDS)
    resp = await client.post("/api/auth/register", json=CREDS)
    assert resp.status_code == 409


async def test_login_returns_token(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=CREDS)
    resp = await client.post("/api/auth/login", json=CREDS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


async def test_login_wrong_password_rejected(client: AsyncClient) -> None:
    await client.post("/api/auth/register", json=CREDS)
    resp = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": "wrongpassword"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code in (401, 403)


async def test_me_returns_current_user(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "owner@example.com"
