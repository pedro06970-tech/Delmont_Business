import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OpportunityStatus = Literal["open", "won", "lost"]
ClosedOpportunityStatus = Literal["won", "lost"]


class SalesOpportunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: uuid.UUID
    customer_id: uuid.UUID
    product_name: str = Field(min_length=1, max_length=200)

    @field_validator("product_name")
    @classmethod
    def clean_product(cls, value: str) -> str:
        return " ".join(value.split())


class SalesOpportunityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_name: str = Field(min_length=1, max_length=200)

    @field_validator("product_name")
    @classmethod
    def clean_product(cls, value: str) -> str:
        return " ".join(value.split())


class SalesOpportunityClose(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ClosedOpportunityStatus
    lost_reason: str | None = Field(default=None, max_length=500)

    @field_validator("lost_reason")
    @classmethod
    def clean_reason(cls, value: str | None) -> str | None:
        clean = " ".join(value.split()) if value else None
        return clean or None

    @model_validator(mode="after")
    def validate_reason(self) -> "SalesOpportunityClose":
        if self.status == "won" and self.lost_reason is not None:
            raise ValueError("Motivo de desistência só pode ser informado para venda perdida.")
        return self


class SalesOpportunityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    previous_status: str | None
    new_status: str
    performed_by_user_id: uuid.UUID
    performed_by_name: str
    lost_reason: str | None
    occurred_at: datetime


class SalesOpportunityResponse(BaseModel):
    id: uuid.UUID
    store_id: uuid.UUID
    customer_id: uuid.UUID
    customer_name: str
    product_name: str
    status: OpportunityStatus
    created_by_user_id: uuid.UUID
    created_by_name: str
    closed_by_user_id: uuid.UUID | None
    closed_by_name: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    lost_reason: str | None
    reminder_count: int = 0


class SalesOpportunityDetailResponse(SalesOpportunityResponse):
    events: list[SalesOpportunityEventResponse]


class SalesOpportunityPage(BaseModel):
    items: list[SalesOpportunityResponse]
    total: int
    page: int
    page_size: int
    pages: int


class DashboardPeriod(BaseModel):
    timezone: str
    date_from: date
    date_to: date
    start_utc: datetime
    end_utc_exclusive: datetime


class DashboardMetrics(BaseModel):
    distinct_leads: int
    open_opportunities: int
    scheduled_reminders: int
    accepted_messages: int
    won_opportunities: int
    lost_opportunities: int
    conversion_rate: float
    conversion_has_basis: bool
    conversion_definition: str


class DashboardEvolutionPoint(BaseModel):
    date: date
    reminders: int


class CollaboratorPerformance(BaseModel):
    user_id: uuid.UUID
    user_name: str
    opportunities_created: int
    opportunities_won: int
    reminders_created: int


class CommercialDashboardResponse(BaseModel):
    period: DashboardPeriod
    metrics: DashboardMetrics
    reminder_evolution: list[DashboardEvolutionPoint]
    collaborator_performance: list[CollaboratorPerformance]
