"""Alert rule model — a per-device threshold on a sensor."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    sensor_name: Mapped[str] = mapped_column(String(64))
    # One of: lt, lte, gt, gte.
    comparator: Mapped[str] = mapped_column(String(3))
    threshold: Mapped[float] = mapped_column(Double)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
