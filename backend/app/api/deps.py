"""Shared API dependencies (current-user resolution)."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User

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
