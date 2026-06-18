"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check")
async def health() -> dict[str, str]:
    """Cheap liveness probe — returns ok if the API process is serving."""
    return {"status": "ok"}


@router.get("/health/db", summary="Database readiness check")
async def health_db(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    """Readiness probe — confirms the database is reachable."""
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}
