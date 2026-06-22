"""RoboSense FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.devices import router as devices_router
from app.api.health import router as health_router
from app.api.stream import router as stream_router
from app.api.telemetry import router as telemetry_router
from app.core.config import settings
from app.db.init_db import init_models
from app.db.session import engine
from app.db.timescale import apply_policies

logger = logging.getLogger("robosense")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup so the stack is usable after `make up`
    # with no separate migration step.
    await init_models()
    # Continuous aggregate + compression/retention policies. Best-effort: a
    # failure here (e.g. a transient DB hiccup) shouldn't stop the API serving.
    try:
        await apply_policies(engine)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to apply TimescaleDB policies")
    yield


_DESCRIPTION = """
A focused, self-hostable telemetry backend for robots and embedded devices.

**Two ways in:**

* Devices **ingest** with a per-device API key (`X-API-Key` header) — see
  `POST /api/telemetry`.
* The dashboard user authenticates with a **JWT** (`Authorization: Bearer …`)
  from `/api/auth/login` to manage devices, query telemetry, and configure alerts.

Telemetry is stored in a TimescaleDB hypertable; queries support `time_bucket`
downsampling.
"""

_TAGS_METADATA = [
    {"name": "auth", "description": "Register, log in, and inspect the current user."},
    {"name": "devices", "description": "Create, list, rename, delete devices and rotate API keys."},
    {"name": "telemetry", "description": "Ingest readings (API key) and query them (JWT)."},
    {"name": "alerts", "description": "Per-device threshold rules and their live status."},
    {"name": "health", "description": "Liveness and database-readiness probes."},
    {"name": "meta", "description": "Service metadata."},
]

app = FastAPI(
    title="RoboSense API",
    description=_DESCRIPTION,
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=_TAGS_METADATA,
    license_info={"name": "MIT", "url": "https://opensource.org/license/mit"},
    contact={"name": "RoboSense", "url": "https://github.com/MohamedAymanOuchker/RoboSense"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(devices_router, prefix="/api")
app.include_router(telemetry_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(stream_router, prefix="/api")


@app.get("/", tags=["meta"], summary="Service metadata")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
