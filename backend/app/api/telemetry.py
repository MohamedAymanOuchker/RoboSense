"""Telemetry ingestion and query endpoints.

- ``POST /api/telemetry`` — device-authenticated (``X-API-Key``) ingestion. The
  flat key/value payload is fanned out into one row per sensor.
- ``GET /api/telemetry`` — user-authenticated (JWT) query with optional Timescale
  ``time_bucket`` downsampling, time range, sensor filter, and pagination.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_ingesting_device, get_rate_limiter
from app.core.rate_limit import FixedWindowRateLimiter
from app.db.session import get_session
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User
from app.schemas.telemetry import (
    IngestResult,
    TelemetryIngest,
    TelemetryPoint,
    TelemetryQueryResult,
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

_RESERVED_KEYS = {"device_id", "timestamp"}

# Allowlist of downsampling bucket sizes (param value -> interval). Keeping this
# closed avoids interpolating arbitrary interval strings into the query.
_BUCKETS: dict[str, timedelta] = {
    "1s": timedelta(seconds=1),
    "10s": timedelta(seconds=10),
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}

_AGGREGATES = {"avg": func.avg, "min": func.min, "max": func.max}


def _extract_readings(payload: TelemetryIngest) -> tuple[dict[str, float], list[str]]:
    """Split the flexible payload into numeric sensor readings and invalid keys."""
    readings: dict[str, float] = {}
    invalid: list[str] = []
    for key, value in (payload.model_extra or {}).items():
        if key in _RESERVED_KEYS:
            continue
        # bool is a subclass of int — reject it explicitly so flags aren't stored
        # as 0/1 doubles by accident.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            invalid.append(key)
        else:
            readings[key] = float(value)
    return readings, invalid


@router.post(
    "",
    response_model=IngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a telemetry reading (X-API-Key auth)",
)
async def ingest(
    payload: TelemetryIngest,
    device: Device = Depends(get_ingesting_device),
    limiter: FixedWindowRateLimiter = Depends(get_rate_limiter),
    session: AsyncSession = Depends(get_session),
) -> IngestResult:
    allowed, retry_after = limiter.check(str(device.id))
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded for this device",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    readings, invalid = _extract_readings(payload)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Non-numeric sensor values for: {', '.join(sorted(invalid))}",
        )
    if not readings:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No numeric sensor readings provided",
        )

    ts = payload.timestamp or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    rows = [
        {"time": ts, "device_id": device.id, "sensor_name": name, "value": value}
        for name, value in readings.items()
    ]
    await session.execute(pg_insert(Telemetry).values(rows).on_conflict_do_nothing())
    await session.commit()

    return IngestResult(
        status="accepted",
        device_id=device.id,
        points_written=len(rows),
        time=ts,
    )


@router.get(
    "",
    response_model=TelemetryQueryResult,
    summary="Query telemetry (JWT auth), optionally downsampled",
)
async def query_telemetry(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    sensor_name: str | None = Query(default=None),
    start: datetime | None = Query(default=None, description="Inclusive lower bound"),
    end: datetime | None = Query(default=None, description="Exclusive upper bound"),
    bucket: str | None = Query(
        default=None, description=f"Downsample interval, one of: {', '.join(_BUCKETS)}"
    ),
    agg: str = Query(default="avg", description="avg | min | max (used with bucket)"),
    order: str = Query(default="asc", description="asc | desc by time"),
    limit: int = Query(default=1000, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
) -> TelemetryQueryResult:
    # Ownership check: a user may only read their own devices' telemetry.
    device = await session.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if bucket is not None and bucket not in _BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid bucket; choose one of: {', '.join(_BUCKETS)}",
        )
    if agg not in _AGGREGATES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid agg; choose one of: {', '.join(_AGGREGATES)}",
        )
    if order not in ("asc", "desc"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid order; choose 'asc' or 'desc'",
        )

    conditions = [Telemetry.device_id == device_id]
    if sensor_name is not None:
        conditions.append(Telemetry.sensor_name == sensor_name)
    if start is not None:
        conditions.append(Telemetry.time >= start)
    if end is not None:
        conditions.append(Telemetry.time < end)

    if bucket is not None:
        bucket_col = func.time_bucket(_BUCKETS[bucket], Telemetry.time).label("time")
        value_col = _AGGREGATES[agg](Telemetry.value).label("value")
        time_order = bucket_col.desc() if order == "desc" else bucket_col.asc()
        stmt = (
            select(bucket_col, Telemetry.sensor_name, value_col)
            .where(and_(*conditions))
            .group_by(bucket_col, Telemetry.sensor_name)
            .order_by(time_order, Telemetry.sensor_name)
        )
    else:
        time_order = Telemetry.time.desc() if order == "desc" else Telemetry.time.asc()
        stmt = (
            select(Telemetry.time, Telemetry.sensor_name, Telemetry.value)
            .where(and_(*conditions))
            .order_by(time_order, Telemetry.sensor_name)
        )

    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    points = [TelemetryPoint(time=row[0], sensor_name=row[1], value=float(row[2])) for row in rows]
    return TelemetryQueryResult(
        device_id=device_id,
        sensor_name=sensor_name,
        bucket=bucket,
        agg=agg if bucket is not None else None,
        count=len(points),
        points=points,
    )
