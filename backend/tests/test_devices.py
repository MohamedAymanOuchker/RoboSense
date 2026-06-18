"""Tests for the device-management endpoints."""

from httpx import AsyncClient


async def test_devices_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/devices")
    assert resp.status_code in (401, 403)


async def test_create_device_returns_key_once(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/devices", json={"name": "robot001"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "robot001"
    assert body["api_key"].startswith("rsk_")
    # The prefix is a non-secret label derived from the full key.
    assert body["api_key"].startswith(body["api_key_prefix"])

    # The full key is never returned again by the read endpoints.
    listed = (await auth_client.get("/api/devices")).json()
    assert "api_key" not in listed[0]


async def test_list_devices(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/devices", json={"name": "a"})
    await auth_client.post("/api/devices", json={"name": "b"})
    resp = await auth_client.get("/api/devices")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()]
    assert names == ["a", "b"]


async def test_rename_device(auth_client: AsyncClient) -> None:
    device_id = (await auth_client.post("/api/devices", json={"name": "old"})).json()["id"]
    resp = await auth_client.patch(f"/api/devices/{device_id}", json={"name": "new"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "new"


async def test_delete_device(auth_client: AsyncClient) -> None:
    device_id = (await auth_client.post("/api/devices", json={"name": "tmp"})).json()["id"]
    resp = await auth_client.delete(f"/api/devices/{device_id}")
    assert resp.status_code == 204
    assert (await auth_client.get(f"/api/devices/{device_id}")).status_code == 404


async def test_regenerate_key_changes_key(auth_client: AsyncClient) -> None:
    created = (await auth_client.post("/api/devices", json={"name": "rotate"})).json()
    resp = await auth_client.post(f"/api/devices/{created['id']}/regenerate-key")
    assert resp.status_code == 200
    rotated = resp.json()
    assert rotated["api_key"] != created["api_key"]
    assert rotated["api_key_prefix"] != created["api_key_prefix"]


async def test_cannot_access_other_users_device(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    # Device owned by the first (auth_client) user.
    device_id = (await auth_client.post("/api/devices", json={"name": "private"})).json()["id"]

    # A second, separate user.
    other = {"email": "mallory@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=other)
    token = (await client.post("/api/auth/login", json=other)).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get(f"/api/devices/{device_id}", headers=headers)).status_code == 404
