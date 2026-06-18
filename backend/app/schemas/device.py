"""Device request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DeviceUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class DeviceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    api_key_prefix: str
    created_at: datetime


class DeviceWithKey(DeviceRead):
    """Returned only on create / regenerate — includes the plaintext API key,
    which is never retrievable again."""

    api_key: str
