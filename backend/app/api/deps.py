"""Shared API dependencies (current-user resolution, device API-key auth)."""

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limit import FixedWindowRateLimiter
from app.core.security import decode_access_token, hash_api_key
from app.db.session import get_session
from app.models.device import Device
from app.models.user import User

# --- Dashboard user (JWT) ----------------------------------------------------

_bearer = HTTPBearer(description="JWT access token from /api/auth/login")

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    subject = decode_access_token(credentials.credentials)
    if subject is None:
        raise _credentials_error
    try:
        user_id = int(subject)
    except ValueError as exc:
        raise _credentials_error from exc

    user = await session.get(User, user_id)
    if user is None:
        raise _credentials_error
    return user


# --- Device (X-API-Key) ------------------------------------------------------

_api_key_header = APIKeyHeader(
    name="X-API-Key", description="Per-device API key for telemetry ingestion"
)


async def get_ingesting_device(
    api_key: str = Depends(_api_key_header),
    session: AsyncSession = Depends(get_session),
) -> Device:
    device = await session.scalar(
        select(Device).where(Device.api_key_hash == hash_api_key(api_key))
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return device


# --- Rate limiter ------------------------------------------------------------

_rate_limiter = FixedWindowRateLimiter(
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


def get_rate_limiter() -> FixedWindowRateLimiter:
    return _rate_limiter
