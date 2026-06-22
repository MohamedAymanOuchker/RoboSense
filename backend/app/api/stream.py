"""Live telemetry stream over Server-Sent Events (SSE).

A browser ``EventSource`` can't send an ``Authorization`` header, so this
endpoint authenticates via a ``token`` query parameter (the same JWT). Each
connection subscribes to the in-process broker and emits an SSE ``reading``
event per ingested reading, with periodic heartbeats to keep the connection
alive and detect disconnects.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import get_broker
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.device import Device
from app.models.user import User

router = APIRouter(prefix="/devices", tags=["stream"])

_HEARTBEAT_SECONDS = 15.0


@router.get(
    "/{device_id}/stream",
    summary="Live telemetry stream (SSE). Authenticate with ?token=<JWT>.",
)
async def stream_telemetry(
    device_id: int,
    token: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    subject = decode_access_token(token)
    user = None
    if subject is not None:
        try:
            user = await session.get(User, int(subject))
        except ValueError:
            user = None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )

    device = await session.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    broker = get_broker()
    queue = broker.subscribe(device_id)

    async def event_stream():
        # Starlette cancels this generator when the client disconnects; the
        # `finally` then unsubscribes. The heartbeat keeps the connection warm.
        try:
            yield ": connected\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_SECONDS)
                except TimeoutError:
                    yield ": ping\n\n"  # heartbeat
                    continue
                yield f"event: reading\ndata: {json.dumps(event)}\n\n"
        finally:
            broker.unsubscribe(device_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
