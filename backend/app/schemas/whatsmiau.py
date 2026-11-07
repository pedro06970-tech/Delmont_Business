import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WhatsMiauConfigurationUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instance_name: str = Field(
        min_length=1,
        max_length=40,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    credential_env_var: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    webhook_secret_env_var: str | None = Field(
        default=None,
        max_length=128,
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    is_enabled: bool = True

    @field_validator("instance_name", "credential_env_var")
    @classmethod
    def clean_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("instance_name")
    @classmethod
    def require_alphanumeric_instance(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("O identificador deve conter letra ou número.")
        return value


class WhatsMiauConfigurationResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    instance_name: str
    is_enabled: bool
    dispatch_paused: bool
    connection_state: str
    last_connection_error: str | None
    last_checked_at: datetime | None
    last_dispatch_at: datetime | None
    credential_configured: bool
    webhook_secret_configured: bool
    homologation_ready: bool
    homologation_phone_masked: str | None
    created_at: datetime
    updated_at: datetime


class ReminderDeliveryAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reminder_id: uuid.UUID
    store_id: uuid.UUID
    configuration_id: uuid.UUID | None
    attempt_number: int
    status: str
    provider_message_id: str | None
    provider_status: str | None
    error_category: str | None
    sanitized_error: str | None
    http_status: int | None
    started_at: datetime
    finished_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None


class HomologationNumberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=8, max_length=40)
    confirm_authorized: Literal[True]


class WhatsMiauReadinessResponse(BaseModel):
    store_id: uuid.UUID
    configured: bool
    enabled: bool
    dispatch_paused: bool
    connection_state: str
    last_checked_at: datetime | None
    credential_configured: bool
    ready_to_schedule: bool
    homologation_only: bool
    homologation_ready: bool


class WhatsMiauWebhookData(BaseModel):
    model_config = ConfigDict(extra="allow")

    messageId: str | None = None
    keyId: str | None = None
    status: str | None = None


class WhatsMiauWebhookEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: str
    instance: str
    data: WhatsMiauWebhookData


class WhatsMiauWebhookResponse(BaseModel):
    processed: bool
