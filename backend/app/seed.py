"""Seed the database with a demo user, device, and 24h of fake telemetry.

Run with ``make seed`` (or ``python -m app.seed`` inside the backend container).
Idempotent: re-running replaces the demo device's telemetry and rotates its API
key so the printed key is always usable.
"""

import asyncio
import math
import random
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.security import (
    api_key_prefix,
    generate_api_key,
    hash_api_key,
    hash_password,
)
from app.db.init_db import init_models
from app.db.session import AsyncSessionLocal, engine
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User

# Note: must be a valid address per EmailStr (the login endpoint validates it),
# so avoid reserved/special-use TLDs like ".local".
DEMO_EMAIL = "demo@robosense.dev"
DEMO_PASSWORD = "demodemo123"
DEVICE_NAME = "seed-rover"

HOURS = 24
STEP = timedelta(seconds=30)
CHUNK = 5000


def _generate_rows(device_id: int) -> list[dict]:
    """A day of plausible rover telemetry: diurnal temperature, draining battery,
    noisy speed, and humidity. Battery dips below 20% near the end so the
    threshold-alert feature has something to flag."""
    now = datetime.now(UTC)
    steps = int(HOURS * 3600 / STEP.total_seconds())
    start = now - HOURS * timedelta(hours=1)
    battery = 100.0
    rows: list[dict] = []
    t = start
    for i in range(steps):
        battery = max(5.0, battery - 0.03 - random.random() * 0.01)
        sample = {
            "temperature": 24 + 4 * math.sin(i / 120) + random.gauss(0, 0.3),
            "battery": battery,
            "speed": max(0.0, 0.7 + 0.5 * math.sin(i / 60) + random.gauss(0, 0.1)),
            "humidity": 45 + 10 * math.sin(i / 200) + random.gauss(0, 0.5),
        }
        for sensor_name, value in sample.items():
            rows.append(
                {
                    "time": t,
                    "device_id": device_id,
                    "sensor_name": sensor_name,
                    "value": round(value, 3),
                }
            )
        t += STEP
    return rows


async def seed() -> None:
    await init_models()

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD))
            session.add(user)
            await session.commit()
            await session.refresh(user)

        api_key = generate_api_key()
        device = await session.scalar(
            select(Device).where(Device.user_id == user.id, Device.name == DEVICE_NAME)
        )
        if device is None:
            device = Device(
                user_id=user.id,
                name=DEVICE_NAME,
                api_key_hash=hash_api_key(api_key),
                api_key_prefix=api_key_prefix(api_key),
            )
            session.add(device)
        else:
            device.api_key_hash = hash_api_key(api_key)
            device.api_key_prefix = api_key_prefix(api_key)
        await session.commit()
        await session.refresh(device)

        # Replace any prior telemetry for this device so the seed is idempotent.
        await session.execute(delete(Telemetry).where(Telemetry.device_id == device.id))
        await session.commit()

        rows = _generate_rows(device.id)
        for i in range(0, len(rows), CHUNK):
            await session.execute(
                pg_insert(Telemetry).values(rows[i : i + CHUNK]).on_conflict_do_nothing()
            )
        await session.commit()

    await engine.dispose()

    print(f"Seeded {len(rows)} telemetry points for device id={device.id} ({DEVICE_NAME}).")
    print(f"Demo login:  {DEMO_EMAIL} / {DEMO_PASSWORD}")
    print("Device API key (use as the X-API-Key header):")
    print(f"  {api_key}")


if __name__ == "__main__":
    asyncio.run(seed())
