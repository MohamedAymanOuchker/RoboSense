"""Telemetry ingest/query schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryIngest(BaseModel):
    """Flexible ingest payload.

    The device is identified by its ``X-API-Key`` header, so ``device_id`` here is
    just an optional label. ``timestamp`` is optional (lets a device flush buffered
    readings with their original time after a reconnect); it defaults to the server
    receive time. Every other top-level key is treated as ``sensor_name: value``
    and must be numeric.
    """

    model_config = ConfigDict(extra="allow")

    device_id: str | None = Field(
        default=None, description="Optional label; the device is identified by its API key."
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Optional reading time (ISO 8601). Defaults to server receive time.",
    )


class IngestResult(BaseModel):
    status: str
    device_id: int
    points_written: int
    time: datetime


class TelemetryPoint(BaseModel):
    time: datetime
    sensor_name: str
    value: float


class TelemetryQueryResult(BaseModel):
    device_id: int
    sensor_name: str | None
    bucket: str | None
    agg: str | None
    count: int
    points: list[TelemetryPoint]


class SensorSnapshot(BaseModel):
    sensor_name: str
    value: float
    time: datetime


class LatestSnapshot(BaseModel):
    device_id: int
    last_seen: datetime | None
    readings: list[SensorSnapshot]
