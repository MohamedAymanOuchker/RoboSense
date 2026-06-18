"""ORM models. Importing this package registers every model on the shared
``Base.metadata`` so schema creation (and tests) see all tables."""

from app.models.device import Device
from app.models.user import User

__all__ = ["Device", "User"]
