import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=8, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, min_length=8, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ConsentRequest(BaseModel):
    source: str = Field(min_length=2, max_length=120)

    @field_validator("source")
    @classmethod
    def clean_source(cls, value: str) -> str:
        return value.strip()


class ConsentEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    source: str | None
    performed_by_user_id: uuid.UUID
    occurred_at: datetime


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    phone_e164: str
    notes: str | None
    is_active: bool
    has_consent: bool
    consented_at: datetime | None
    consent_source: str | None
    consent_revoked_at: datetime | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class CustomerDetailResponse(CustomerResponse):
    consent_history: list[ConsentEventResponse]


class CustomerPage(BaseModel):
    items: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    pages: int


class MessageTemplateCreate(BaseModel):
    store_id: uuid.UUID
    name: str = Field(min_length=2, max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    is_active: bool = True

    @field_validator("name", "content")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip()


class MessageTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    is_active: bool | None = None

    @field_validator("name", "content")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class MessageTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    name: str
    content: str
    is_active: bool
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class MessagePreviewRequest(BaseModel):
    customer_name: str = Field(default="Cliente", min_length=1, max_length=120)
    product: str = Field(default="produto", min_length=1, max_length=200)


class MessagePreviewResponse(BaseModel):
    rendered_content: str
