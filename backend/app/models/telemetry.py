"""Telemetry model — one row per (sensor reading).

Stored in a TimescaleDB **hypertable** partitioned on ``time`` (configured in
``app.db.init_db``). The composite primary key includes ``time`` (required by
Timescale for the unique constraint) and dedupes a device's reading for a given
sensor at a given instant. A descending ``(device_id, sensor_name, time)`` index
accelerates the common "recent readings for a device/sensor" query.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Telemetry(Base):
    __tablename__ = "telemetry"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True
    )
    sensor_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Double)


Index(
    "ix_telemetry_device_sensor_time",
    Telemetry.device_id,
    Telemetry.sensor_name,
    Telemetry.time.desc(),
)
