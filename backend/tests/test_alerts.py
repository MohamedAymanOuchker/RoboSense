"""Tests for alert rules, alert status, and the latest-snapshot endpoint."""

from httpx import AsyncClient


async def _device_with_key(auth_client: AsyncClient, name: str = "rover") -> tuple[int, str]:
    resp = (await auth_client.post("/api/devices", json={"name": name})).json()
    return resp["id"], resp["api_key"]


async def _ingest(auth_client: AsyncClient, key: str, **sensors: float) -> None:
    await auth_client.post("/api/telemetry", json=sensors, headers={"X-API-Key": key})


# --- Rule CRUD ---------------------------------------------------------------


async def test_create_and_list_alert_rule(auth_client: AsyncClient) -> None:
    device_id, _ = await _device_with_key(auth_client)
    resp = await auth_client.post(
        f"/api/devices/{device_id}/alerts",
        json={"sensor_name": "battery", "comparator": "lt", "threshold": 20},
    )
    assert resp.status_code == 201
    rule = resp.json()
    assert rule["sensor_name"] == "battery"
    assert rule["comparator"] == "lt"
    assert rule["threshold"] == 20

    listed = await auth_client.get(f"/api/devices/{device_id}/alerts")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_create_alert_rejects_bad_comparator(auth_client: AsyncClient) -> None:
    device_id, _ = await _device_with_key(auth_client)
    resp = await auth_client.post(
        f"/api/devices/{device_id}/alerts",
        json={"sensor_name": "battery", "comparator": "approximately", "threshold": 20},
    )
    assert resp.status_code == 422


async def test_delete_alert_rule(auth_client: AsyncClient) -> None:
    device_id, _ = await _device_with_key(auth_client)
    rule_id = (
        await auth_client.post(
            f"/api/devices/{device_id}/alerts",
            json={"sensor_name": "battery", "comparator": "lt", "threshold": 20},
        )
    ).json()["id"]
    resp = await auth_client.delete(f"/api/devices/{device_id}/alerts/{rule_id}")
    assert resp.status_code == 204
    assert (await auth_client.get(f"/api/devices/{device_id}/alerts")).json() == []


async def test_alert_rules_require_ownership(auth_client: AsyncClient, client: AsyncClient) -> None:
    device_id, _ = await _device_with_key(auth_client)
    other = {"email": "snoop@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=other)
    token = (await client.post("/api/auth/login", json=other)).json()["access_token"]
    resp = await client.get(
        f"/api/devices/{device_id}/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# --- Status evaluation -------------------------------------------------------


async def test_alert_status_triggered(auth_client: AsyncClient) -> None:
    device_id, key = await _device_with_key(auth_client)
    await _ingest(auth_client, key, battery=15.0)
    await auth_client.post(
        f"/api/devices/{device_id}/alerts",
        json={"sensor_name": "battery", "comparator": "lt", "threshold": 20},
    )
    status = await auth_client.get(f"/api/devices/{device_id}/alerts/status")
    assert status.status_code == 200
    body = status.json()
    assert len(body) == 1
    assert body[0]["triggered"] is True
    assert body[0]["latest_value"] == 15.0


async def test_alert_status_not_triggered(auth_client: AsyncClient) -> None:
    device_id, key = await _device_with_key(auth_client)
    await _ingest(auth_client, key, battery=80.0)
    await auth_client.post(
        f"/api/devices/{device_id}/alerts",
        json={"sensor_name": "battery", "comparator": "lt", "threshold": 20},
    )
    body = (await auth_client.get(f"/api/devices/{device_id}/alerts/status")).json()
    assert body[0]["triggered"] is False
    assert body[0]["latest_value"] == 80.0


async def test_alert_status_no_data(auth_client: AsyncClient) -> None:
    device_id, _ = await _device_with_key(auth_client)
    await auth_client.post(
        f"/api/devices/{device_id}/alerts",
        json={"sensor_name": "battery", "comparator": "lt", "threshold": 20},
    )
    body = (await auth_client.get(f"/api/devices/{device_id}/alerts/status")).json()
    assert body[0]["triggered"] is False
    assert body[0]["latest_value"] is None


# --- Latest snapshot ---------------------------------------------------------


async def test_latest_snapshot(auth_client: AsyncClient) -> None:
    device_id, key = await _device_with_key(auth_client)
    await _ingest(auth_client, key, temperature=21.0, battery=55.0)
    resp = await auth_client.get(f"/api/telemetry/latest?device_id={device_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["last_seen"] is not None
    snapshot = {r["sensor_name"]: r["value"] for r in body["readings"]}
    assert snapshot == {"temperature": 21.0, "battery": 55.0}


async def test_latest_snapshot_returns_most_recent(auth_client: AsyncClient) -> None:
    device_id, key = await _device_with_key(auth_client)
    headers = {"X-API-Key": key}
    await auth_client.post(
        "/api/telemetry",
        json={"timestamp": "2026-06-01T00:00:00Z", "battery": 90.0},
        headers=headers,
    )
    await auth_client.post(
        "/api/telemetry",
        json={"timestamp": "2026-06-01T00:01:00Z", "battery": 30.0},  # newer
        headers=headers,
    )
    body = (await auth_client.get(f"/api/telemetry/latest?device_id={device_id}")).json()
    snapshot = {r["sensor_name"]: r["value"] for r in body["readings"]}
    assert snapshot["battery"] == 30.0
