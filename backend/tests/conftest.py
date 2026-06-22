"""Shared pytest fixtures.

Tests run against a **dedicated** database (``<dbname>_test``) on the same
Postgres/Timescale server, auto-created if missing. This isolates the suite from
the application's data so test teardown can freely drop and recreate the schema
without ever touching the dev/production database.

A NullPool engine is used so each operation gets a fresh connection bound to the
current event loop, keeping function-scoped async tests free of
"future attached to a different loop" errors.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (register models on Base.metadata)
from app.api.deps import get_rate_limiter
from app.core.config import settings
from app.core.rate_limit import FixedWindowRateLimiter
from app.db.base import Base
from app.db.init_db import prepare_database
from app.db.session import get_session
from app.main import app

_app_url = make_url(settings.database_url)
_test_db_name = f"{_app_url.database}_test"
_test_url = _app_url.set(database=_test_db_name)
_admin_url = _app_url.set(database="postgres")

test_engine = create_async_engine(_test_url, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


async def _override_get_session() -> AsyncGenerator:
    async with TestSessionLocal() as session:
        yield session


async def _ensure_test_database() -> None:
    """Create the dedicated test database if it does not already exist."""
    admin_engine = create_async_engine(_admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": _test_db_name},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{_test_db_name}"'))
    finally:
        await admin_engine.dispose()


async def _drop_continuous_aggregate() -> None:
    """Drop the continuous aggregate if a test created one. It depends on the
    telemetry hypertable, so it must go before ``drop_all`` (which drops that
    table) — and it can't be dropped inside a transaction."""
    async with test_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS telemetry_summary CASCADE"))


@pytest_asyncio.fixture(autouse=True)
async def _prepare_database() -> AsyncGenerator[None, None]:
    """Ensure the test database exists and give every test a clean schema."""
    await _ensure_test_database()
    await _drop_continuous_aggregate()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # Reuse the app's real schema-prep path (extension + tables + hypertable).
        await prepare_database(conn)
    yield
    await _drop_continuous_aggregate()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _permissive_rate_limiter():
    """Isolate every test from the shared singleton ingest limiter with a fresh,
    generous one. Tests that exercise rate limiting override it themselves."""
    limiter = FixedWindowRateLimiter(max_requests=10_000, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(get_rate_limiter, None)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the ASGI app, using the test database."""
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """A client pre-authenticated as a freshly registered user."""
    creds = {"email": "owner@example.com", "password": "supersecret123"}
    await client.post("/api/auth/register", json=creds)
    resp = await client.post("/api/auth/login", json=creds)
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
