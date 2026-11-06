import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def validate_future(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Informe data e hora com fuso horário.")
    if value <= datetime.now(UTC):
        raise ValueError("A data programada deve estar no futuro.")
    return value


class ReminderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    customer_id: uuid.UUID
    message_template_id: uuid.UUID
    product_interest: str = Field(min_length=1, max_length=200)
    scheduled_for: datetime

    _future_schedule = field_validator("scheduled_for")(validate_future)

    @field_validator("product_interest")
    @classmethod
    def clean_product(cls, value: str) -> str:
        return " ".join(value.split())


class ReminderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_template_id: uuid.UUID | None = None
    product_interest: str | None = Field(default=None, min_length=1, max_length=200)
    scheduled_for: datetime | None = None

    @field_validator("scheduled_for")
    @classmethod
    def future_schedule(cls, value: datetime | None) -> datetime | None:
        return validate_future(value) if value is not None else None

    @field_validator("product_interest")
    @classmethod
    def clean_product(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "ReminderUpdate":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Campos de edição não podem ser nulos.")
        return self


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    customer_id: uuid.UUID
    message_template_id: uuid.UUID
    product_interest: str
    scheduled_for: datetime
    rendered_message: str
    status: str
    created_by_user_id: uuid.UUID
    cancelled_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class ReminderPage(BaseModel):
    items: list[ReminderResponse]
    total: int
    page: int
    page_size: int
    pages: int


class ProductSaleCompleted(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    customer_id: uuid.UUID
    product_interest: str = Field(min_length=1, max_length=200)

    @field_validator("product_interest")
    @classmethod
    def clean_product(cls, value: str) -> str:
        return " ".join(value.split())


class ProductCancellationResponse(BaseModel):
    cancelled_count: int
