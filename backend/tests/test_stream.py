"""Tests for the live SSE telemetry stream and its in-process broker."""

import asyncio
import json

from httpx import AsyncClient

from app.api.stream import stream_telemetry
from app.core.events import TelemetryBroker, get_broker
from tests.conftest import TestSessionLocal


async def test_broker_delivers_to_subscribers() -> None:
    broker = TelemetryBroker()
    q1 = broker.subscribe(1)
    q2 = broker.subscribe(1)
    other = broker.subscribe(2)

    broker.publish(1, {"hello": "world"})

    assert q1.get_nowait() == {"hello": "world"}
    assert q2.get_nowait() == {"hello": "world"}
    assert other.empty()  # device 2 gets nothing

    broker.unsubscribe(1, q1)
    broker.publish(1, {"again": 1})
    assert q2.get_nowait() == {"again": 1}
    assert broker.subscriber_count(1) == 1


async def test_stream_requires_token(auth_client: AsyncClient) -> None:
    device_id = (await auth_client.post("/api/devices", json={"name": "s"})).json()["id"]
    resp = await auth_client.get(f"/api/devices/{device_id}/stream")
    assert resp.status_code == 401


async def test_stream_rejects_other_users_device(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    device_id = (await auth_client.post("/api/devices", json={"name": "s2"})).json()["id"]
    other = {"email": "streamsnoop@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=other)
    token = (await client.post("/api/auth/login", json=other)).json()["access_token"]
    resp = await client.get(f"/api/devices/{device_id}/stream?token={token}")
    assert resp.status_code == 404


async def test_ingest_publishes_to_broker(auth_client: AsyncClient) -> None:
    """Ingesting a reading fans it out to the in-process broker."""
    dev = (await auth_client.post("/api/devices", json={"name": "pub"})).json()
    device_id, key = dev["id"], dev["api_key"]

    queue = get_broker().subscribe(device_id)
    try:
        await auth_client.post(
            "/api/telemetry", json={"temperature": 42.0}, headers={"X-API-Key": key}
        )
        event = await asyncio.wait_for(queue.get(), timeout=5)
    finally:
        get_broker().unsubscribe(device_id, queue)

    assert event["readings"]["temperature"] == 42.0


async def test_stream_yields_published_event(auth_client: AsyncClient) -> None:
    """The SSE endpoint emits a `reading` event for data published to its device.

    The endpoint's async generator is driven directly: httpx's in-process ASGI
    transport buffers responses, so it can't read an open-ended SSE stream.
    """
    token = auth_client.headers["Authorization"].split()[1]
    device_id = (await auth_client.post("/api/devices", json={"name": "live"})).json()["id"]

    async with TestSessionLocal() as session:
        response = await stream_telemetry(device_id=device_id, token=token, session=session)
        chunks = response.body_iterator

        first = await asyncio.wait_for(chunks.__anext__(), timeout=5)
        assert "connected" in first

        get_broker().publish(device_id, {"time": "t", "readings": {"temperature": 42.0}})
        chunk = await asyncio.wait_for(chunks.__anext__(), timeout=5)
        await chunks.aclose()

    assert chunk.startswith("event: reading")
    payload = json.loads(chunk.split("data:", 1)[1].strip())
    assert payload["readings"]["temperature"] == 42.0
