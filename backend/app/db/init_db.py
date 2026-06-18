"""Schema initialization.

For a single-service, self-hostable app we favour create-on-startup over a
migration tool: it keeps the quickstart to one command with no migrate step.
Importing ``app.models`` registers every table on ``Base.metadata``.

``prepare_database`` is the single source of truth for schema setup (extension,
tables, Timescale hypertable) and is reused by both app startup and the test
fixtures so they can never drift.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

import app.models  # noqa: F401  (registers models on Base.metadata)
from app.db.base import Base
from app.db.session import engine


async def prepare_database(conn: AsyncConnection) -> None:
    """Ensure the Timescale extension, ORM tables, and hypertable exist."""
    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
    await conn.run_sync(Base.metadata.create_all)
    await conn.execute(text("SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE)"))


async def init_models() -> None:
    async with engine.begin() as conn:
        await prepare_database(conn)
