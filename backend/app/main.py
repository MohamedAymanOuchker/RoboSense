"""RoboSense FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings

app = FastAPI(
    title="RoboSense API",
    description=(
        "A focused, self-hostable telemetry backend for robots and embedded "
        "devices. Devices POST sensor readings; the dashboard reads them back."
    ),
    version="0.1.0",
)

app.include_router(health_router, prefix="/api")


@app.get("/", tags=["meta"], summary="Service metadata")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
