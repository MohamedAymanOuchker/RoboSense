"""RoboSense FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.alerts import router as alerts_router
from app.api.auth import router as auth_router
from app.api.devices import router as devices_router
from app.api.health import router as health_router
from app.api.telemetry import router as telemetry_router
from app.core.config import settings
from app.db.init_db import init_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup so the stack is usable after `make up`
    # with no separate migration step.
    await init_models()
    yield


app = FastAPI(
    title="RoboSense API",
    description=(
        "A focused, self-hostable telemetry backend for robots and embedded "
        "devices. Devices POST sensor readings; the dashboard reads them back."
    ),
    version="0.1.0",
    lifespan=lifespan,
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


@app.get("/", tags=["meta"], summary="Service metadata")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
