"""Alert rule request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Comparator = Literal["lt", "lte", "gt", "gte"]


class AlertRuleCreate(BaseModel):
    sensor_name: str = Field(min_length=1, max_length=64)
    comparator: Comparator
    threshold: float


class AlertRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    sensor_name: str
    comparator: Comparator
    threshold: float
    created_at: datetime


class AlertStatus(BaseModel):
    """A rule evaluated against the sensor's most recent reading."""

    rule_id: int
    sensor_name: str
    comparator: Comparator
    threshold: float
    latest_value: float | None
    latest_time: datetime | None
    triggered: bool
