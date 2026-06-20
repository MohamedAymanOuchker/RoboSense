"""Tests for the rolling z-score anomaly endpoint."""

from httpx import AsyncClient


async def _device_key(auth_client: AsyncClient, name: str) -> tuple[int, str]:
    r = (await auth_client.post("/api/devices", json={"name": name})).json()
    return r["id"], r["api_key"]


async def _ingest_at(auth_client: AsyncClient, key: str, minute: int, value: float) -> None:
    ts = f"2026-06-01T{minute // 60:02d}:{minute % 60:02d}:00Z"
    await auth_client.post(
        "/api/telemetry",
        json={"timestamp": ts, "temperature": value},
        headers={"X-API-Key": key},
    )


async def test_anomaly_flags_outlier(auth_client: AsyncClient) -> None:
    device_id, key = await _device_key(auth_client, "anom")
    # A low-variance baseline (alternating so std > 0), then one large outlier.
    for minute in range(24):
        await _ingest_at(auth_client, key, minute, 50.0 + (minute % 2))
    await _ingest_at(auth_client, key, 24, 200.0)

    resp = await auth_client.get(
        f"/api/telemetry/anomalies?device_id={device_id}&sensor_name=temperature&window=20&z=3"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["anomaly_count"] >= 1
    assert any(abs(a["value"] - 200.0) < 1e-6 for a in body["anomalies"])
    flagged = next(a for a in body["anomalies"] if a["value"] == 200.0)
    assert flagged["zscore"] > 3


async def test_no_anomalies_on_stable_series(auth_client: AsyncClient) -> None:
    device_id, key = await _device_key(auth_client, "stable")
    for minute in range(30):
        await _ingest_at(auth_client, key, minute, 50.0 + (minute % 2))

    resp = await auth_client.get(
        f"/api/telemetry/anomalies?device_id={device_id}&sensor_name=temperature&window=20&z=3"
    )
    assert resp.status_code == 200
    assert resp.json()["anomaly_count"] == 0


async def test_anomalies_require_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/telemetry/anomalies?device_id=1&sensor_name=temperature")
    assert resp.status_code in (401, 403)


async def test_anomalies_other_user_404(auth_client: AsyncClient, client: AsyncClient) -> None:
    device_id, _ = await _device_key(auth_client, "owned-anom")
    other = {"email": "anomsnoop@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=other)
    token = (await client.post("/api/auth/login", json=other)).json()["access_token"]
    resp = await client.get(
        f"/api/telemetry/anomalies?device_id={device_id}&sensor_name=temperature",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
