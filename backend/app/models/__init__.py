"""ORM models. Importing this package registers every model on the shared
``Base.metadata`` so schema creation (and tests) see all tables."""

from app.models.alert import AlertRule
from app.models.device import Device
from app.models.telemetry import Telemetry
from app.models.user import User

__all__ = ["AlertRule", "Device", "Telemetry", "User"]
