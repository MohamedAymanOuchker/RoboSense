"""Device model. A device belongs to one user and authenticates ingestion with
an API key whose SHA-256 hash is stored here (never the plaintext)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # SHA-256 hex digest of the API key — unique so ingestion is an indexed lookup.
    api_key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Short, non-secret prefix shown in the UI to identify the key.
    api_key_prefix: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    owner: Mapped[User] = relationship(back_populates="devices")
