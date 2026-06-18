"""Tests for telemetry ingestion and querying."""

import pytest
from httpx import AsyncClient

from app.api.deps import get_rate_limiter
from app.core.rate_limit import FixedWindowRateLimiter
from app.main import app


@pytest.fixture(autouse=True)
def _permissive_rate_limiter():
    """Isolate tests from the shared singleton limiter with a fresh, generous one."""
    limiter = FixedWindowRateLimiter(max_requests=10_000, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(get_rate_limiter, None)


async def _new_device_key(auth_client: AsyncClient, name: str = "rover") -> str:
    resp = await auth_client.post("/api/devices", json={"name": name})
    return resp.json()["api_key"]


# --- Ingestion ---------------------------------------------------------------


async def test_ingest_requires_api_key(client: AsyncClient) -> None:
    resp = await client.post("/api/telemetry", json={"temperature": 22.0})
    assert resp.status_code in (401, 403)


async def test_ingest_invalid_api_key(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/telemetry", json={"temperature": 22.0}, headers={"X-API-Key": "rsk_nope"}
    )
    assert resp.status_code == 401


async def test_ingest_stores_points(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client)
    resp = await auth_client.post(
        "/api/telemetry",
        json={"device_id": "rover", "temperature": 24.5, "battery": 87, "speed": 0.72},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "accepted"
    assert body["points_written"] == 3  # device_id is a label, not a sensor

    device_id = body["device_id"]
    queried = await auth_client.get(f"/api/telemetry?device_id={device_id}")
    assert queried.status_code == 200
    result = queried.json()
    assert result["count"] == 3
    sensors = {p["sensor_name"] for p in result["points"]}
    assert sensors == {"temperature", "battery", "speed"}


async def test_ingest_rejects_non_numeric(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client)
    resp = await auth_client.post(
        "/api/telemetry", json={"temperature": "hot"}, headers={"X-API-Key": key}
    )
    assert resp.status_code == 422


async def test_ingest_rejects_boolean(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client)
    resp = await auth_client.post(
        "/api/telemetry", json={"online": True}, headers={"X-API-Key": key}
    )
    assert resp.status_code == 422


async def test_ingest_rejects_empty(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client)
    resp = await auth_client.post(
        "/api/telemetry", json={"device_id": "rover"}, headers={"X-API-Key": key}
    )
    assert resp.status_code == 422


async def test_ingest_rate_limited(auth_client: AsyncClient, client: AsyncClient) -> None:
    key = await _new_device_key(auth_client, name="rl-rover")
    limiter = FixedWindowRateLimiter(max_requests=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    headers = {"X-API-Key": key}
    first = await client.post("/api/telemetry", json={"temperature": 1.0}, headers=headers)
    second = await client.post("/api/telemetry", json={"temperature": 2.0}, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 429
    assert "Retry-After" in second.headers


# --- Querying ----------------------------------------------------------------


async def test_query_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/telemetry?device_id=1")
    assert resp.status_code in (401, 403)


async def test_query_other_users_device_404(auth_client: AsyncClient, client: AsyncClient) -> None:
    key = await _new_device_key(auth_client, name="owned")
    device_id = (await auth_client.get("/api/devices")).json()[0]["id"]
    await auth_client.post("/api/telemetry", json={"temperature": 20.0}, headers={"X-API-Key": key})

    other = {"email": "intruder@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=other)
    token = (await client.post("/api/auth/login", json=other)).json()["access_token"]
    resp = await client.get(
        f"/api/telemetry?device_id={device_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_query_sensor_filter(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client, name="filtered")
    await auth_client.post(
        "/api/telemetry",
        json={"temperature": 25.0, "battery": 90.0},
        headers={"X-API-Key": key},
    )
    device_id = (await auth_client.get("/api/devices")).json()[0]["id"]
    resp = await auth_client.get(f"/api/telemetry?device_id={device_id}&sensor_name=battery")
    assert resp.status_code == 200
    points = resp.json()["points"]
    assert len(points) == 1
    assert points[0]["sensor_name"] == "battery"
    assert points[0]["value"] == 90.0


async def test_query_time_bucket_downsampling(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client, name="bucketed")
    headers = {"X-API-Key": key}
    base = "2026-06-01T00:0"
    for minute, value in ((0, 10.0), (1, 20.0), (2, 30.0)):
        await auth_client.post(
            "/api/telemetry",
            json={"timestamp": f"{base}{minute}:00Z", "temperature": value},
            headers=headers,
        )
    device_id = (await auth_client.get("/api/devices")).json()[0]["id"]

    avg = await auth_client.get(
        f"/api/telemetry?device_id={device_id}&sensor_name=temperature&bucket=5m&agg=avg"
    )
    assert avg.status_code == 200
    avg_body = avg.json()
    assert avg_body["bucket"] == "5m"
    assert avg_body["count"] == 1  # all three fall in one 5-minute bucket
    assert avg_body["points"][0]["value"] == pytest.approx(20.0)

    mx = await auth_client.get(
        f"/api/telemetry?device_id={device_id}&sensor_name=temperature&bucket=5m&agg=max"
    )
    assert mx.json()["points"][0]["value"] == pytest.approx(30.0)


async def test_query_rejects_bad_bucket(auth_client: AsyncClient) -> None:
    device_id = (await auth_client.post("/api/devices", json={"name": "bad-bucket"})).json()["id"]
    resp = await auth_client.get(f"/api/telemetry?device_id={device_id}&bucket=7m")
    assert resp.status_code == 422


async def test_query_order_desc_returns_latest_first(auth_client: AsyncClient) -> None:
    key = await _new_device_key(auth_client, name="ordered")
    headers = {"X-API-Key": key}
    await auth_client.post(
        "/api/telemetry",
        json={"timestamp": "2026-06-01T00:00:00Z", "temperature": 1.0},
        headers=headers,
    )
    await auth_client.post(
        "/api/telemetry",
        json={"timestamp": "2026-06-01T01:00:00Z", "temperature": 2.0},
        headers=headers,
    )
    device_id = (await auth_client.get("/api/devices")).json()[0]["id"]

    asc = await auth_client.get(f"/api/telemetry?device_id={device_id}&order=asc")
    assert [p["value"] for p in asc.json()["points"]] == [1.0, 2.0]

    desc = await auth_client.get(f"/api/telemetry?device_id={device_id}&order=desc")
    assert [p["value"] for p in desc.json()["points"]] == [2.0, 1.0]
