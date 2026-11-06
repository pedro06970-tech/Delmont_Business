import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StoreCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class StoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserStoreUpdate(BaseModel):
    store_ids: list[uuid.UUID]


class UserStoresResponse(BaseModel):
    user_id: uuid.UUID
    stores: list[StoreResponse]
