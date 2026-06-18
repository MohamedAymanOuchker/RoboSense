"""Device management endpoints. All routes are scoped to the current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import api_key_prefix, generate_api_key, hash_api_key
from app.db.session import get_session
from app.models.device import Device
from app.models.user import User
from app.schemas.device import DeviceCreate, DeviceRead, DeviceUpdate, DeviceWithKey

router = APIRouter(prefix="/devices", tags=["devices"])


async def _get_owned_device(device_id: int, user: User, session: AsyncSession) -> Device:
    device = await session.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == user.id)
    )
    if device is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.post(
    "",
    response_model=DeviceWithKey,
    status_code=status.HTTP_201_CREATED,
    summary="Create a device (returns its API key once)",
)
async def create_device(
    payload: DeviceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceWithKey:
    api_key = generate_api_key()
    device = Device(
        user_id=current_user.id,
        name=payload.name,
        api_key_hash=hash_api_key(api_key),
        api_key_prefix=api_key_prefix(api_key),
    )
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return DeviceWithKey(
        id=device.id,
        name=device.name,
        api_key_prefix=device.api_key_prefix,
        created_at=device.created_at,
        api_key=api_key,
    )


@router.get("", response_model=list[DeviceRead], summary="List your devices")
async def list_devices(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Device]:
    result = await session.scalars(
        select(Device).where(Device.user_id == current_user.id).order_by(Device.id)
    )
    return list(result)


@router.get("/{device_id}", response_model=DeviceRead, summary="Get one device")
async def get_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Device:
    return await _get_owned_device(device_id, current_user, session)


@router.patch("/{device_id}", response_model=DeviceRead, summary="Rename a device")
async def update_device(
    device_id: int,
    payload: DeviceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Device:
    device = await _get_owned_device(device_id, current_user, session)
    device.name = payload.name
    await session.commit()
    await session.refresh(device)
    return device


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a device",
)
async def delete_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    device = await _get_owned_device(device_id, current_user, session)
    await session.delete(device)
    await session.commit()


@router.post(
    "/{device_id}/regenerate-key",
    response_model=DeviceWithKey,
    summary="Rotate a device's API key (invalidates the old one)",
)
async def regenerate_key(
    device_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> DeviceWithKey:
    device = await _get_owned_device(device_id, current_user, session)
    api_key = generate_api_key()
    device.api_key_hash = hash_api_key(api_key)
    device.api_key_prefix = api_key_prefix(api_key)
    await session.commit()
    await session.refresh(device)
    return DeviceWithKey(
        id=device.id,
        name=device.name,
        api_key_prefix=device.api_key_prefix,
        created_at=device.created_at,
        api_key=api_key,
    )
