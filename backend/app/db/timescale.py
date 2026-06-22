"""TimescaleDB scaling features, applied at startup.

- A **continuous aggregate** (`telemetry_summary`) that pre-materializes hourly
  avg/min/max/count per device+sensor, so historical queries read a small rollup
  instead of scanning raw rows. It is created with ``materialized_only = false``
  so queries transparently combine the materialized rollup with real-time
  aggregation of the most recent (not-yet-materialized) data.
- **Compression** of raw chunks older than a threshold.
- **Retention** that drops raw rows past a threshold (rollups are kept).

These statements cannot run inside a transaction block (CAGG creation and the
policy procedures), so they run in autocommit. All are idempotent, so startup can
re-run them safely.
"""

from sqlalchemy import column, table, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import settings

CAGG_NAME = "telemetry_summary"

# Lightweight Core handle to the continuous aggregate (it is not an ORM model).
telemetry_summary = table(
    CAGG_NAME,
    column("device_id"),
    column("sensor_name"),
    column("bucket"),
    column("avg"),
    column("min"),
    column("max"),
    column("count"),
)

CREATE_CAGG = text(
    f"""
    CREATE MATERIALIZED VIEW IF NOT EXISTS {CAGG_NAME}
    WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
    SELECT device_id,
           sensor_name,
           time_bucket(INTERVAL '1 hour', time) AS bucket,
           avg(value) AS avg,
           min(value) AS min,
           max(value) AS max,
           count(*) AS count
    FROM telemetry
    GROUP BY device_id, sensor_name, bucket
    WITH NO DATA
    """
)

_ADD_REFRESH_POLICY = text(
    f"""
    SELECT add_continuous_aggregate_policy('{CAGG_NAME}',
        start_offset => INTERVAL '7 days',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour',
        if_not_exists => true)
    """
)

_ENABLE_COMPRESSION = text(
    """
    ALTER TABLE telemetry SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'device_id, sensor_name',
        timescaledb.compress_orderby = 'time DESC'
    )
    """
)


async def apply_policies(engine: AsyncEngine) -> None:
    """Idempotently create the rollup and compression/retention policies."""
    async with engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(CREATE_CAGG)
        await conn.execute(_ADD_REFRESH_POLICY)
        await conn.execute(_ENABLE_COMPRESSION)
        if settings.compression_after_days > 0:
            days = int(settings.compression_after_days)
            await conn.execute(
                text(
                    "SELECT add_compression_policy('telemetry', "
                    f"INTERVAL '{days} days', if_not_exists => true)"
                )
            )
        if settings.retention_days > 0:
            days = int(settings.retention_days)
            await conn.execute(
                text(
                    "SELECT add_retention_policy('telemetry', "
                    f"INTERVAL '{days} days', if_not_exists => true)"
                )
            )
