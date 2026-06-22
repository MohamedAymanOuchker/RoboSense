"""Tests for the continuous-aggregate summary endpoint.

The continuous aggregate is created per-test here (rather than in the shared
schema) so it doesn't slow every test; conftest drops it on teardown.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.db.timescale import CREATE_CAGG
from tests.conftest import test_engine


@pytest_asyncio.fixture
async def summary_cagg() -> AsyncGenerator[None, None]:
    async with test_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(CREATE_CAGG)
    yield


async def _device_key(auth_client: AsyncClient, name: str) -> tuple[int, str]:
    r = (await auth_client.post("/api/devices", json={"name": name})).json()
    return r["id"], r["api_key"]


async def test_summary_returns_hourly_rollup(auth_client: AsyncClient, summary_cagg: None) -> None:
    device_id, key = await _device_key(auth_client, "rollup")
    headers = {"X-API-Key": key}
    # Three readings in the 00:00 hour (avg 20), one in the 01:00 hour.
    for minute, value in (("00:10", 10.0), ("00:20", 20.0), ("00:40", 30.0), ("01:10", 100.0)):
        await auth_client.post(
            "/api/telemetry",
            json={"timestamp": f"2026-06-01T{minute}:00Z", "temperature": value},
            headers=headers,
        )

    resp = await auth_client.get(
        f"/api/telemetry/summary?device_id={device_id}&sensor_name=temperature&agg=avg"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["bucket"] == "1h"
    assert body["count"] == 2
    assert body["points"][0]["value"] == pytest.approx(20.0)  # avg of 10/20/30
    assert body["points"][1]["value"] == pytest.approx(100.0)


async def test_summary_max_aggregate(auth_client: AsyncClient, summary_cagg: None) -> None:
    device_id, key = await _device_key(auth_client, "rollup-max")
    headers = {"X-API-Key": key}
    for minute, value in (("00:10", 10.0), ("00:20", 99.0), ("00:40", 30.0)):
        await auth_client.post(
            "/api/telemetry",
            json={"timestamp": f"2026-06-01T{minute}:00Z", "temperature": value},
            headers=headers,
        )
    resp = await auth_client.get(
        f"/api/telemetry/summary?device_id={device_id}&sensor_name=temperature&agg=max"
    )
    assert resp.json()["points"][0]["value"] == pytest.approx(99.0)


async def test_summary_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/telemetry/summary?device_id=1")
    assert resp.status_code in (401, 403)
