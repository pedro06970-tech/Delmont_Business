import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("store_id", "phone_e164", name="uq_customer_store_phone"),
        UniqueConstraint("id", "store_id", name="uq_customers_id_store"),
        Index("ix_customers_store_name", "store_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_e164: Mapped[str] = mapped_column(String(16), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    has_consent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_source: Mapped[str | None] = mapped_column(String(120))
    consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    consent_events = relationship(
        "ConsentEvent",
        back_populates="customer",
        cascade="all, delete-orphan",
        order_by="ConsentEvent.occurred_at",
    )


class ConsentEvent(Base):
    __tablename__ = "customer_consent_events"
    __table_args__ = (
        CheckConstraint("action IN ('granted', 'revoked')", name="ck_consent_event_action"),
        Index("ix_consent_events_customer_time", "customer_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    customer = relationship("Customer", back_populates="consent_events")


class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = (
        UniqueConstraint("store_id", "name", name="uq_message_template_store_name"),
        Index("ix_message_templates_store_active", "store_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'cancelled', 'completed', 'failed')",
            name="ck_reminder_status",
        ),
        CheckConstraint(
            "execution_status IN ('pending', 'claimed', 'sending', 'sent', "
            "'retry_wait', 'uncertain', 'failed')",
            name="ck_reminder_execution_status",
        ),
        Index("ix_reminders_store_status_schedule", "store_id", "status", "scheduled_for"),
        Index(
            "ix_reminders_execution_due",
            "execution_status",
            "next_attempt_at",
            "scheduled_for",
        ),
        Index("ix_reminders_opportunity", "opportunity_id"),
        Index(
            "uq_pending_reminder_identity",
            "store_id",
            "customer_id",
            "message_template_id",
            "product_key",
            "scheduled_for",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        ForeignKeyConstraint(
            ["opportunity_id", "store_id", "customer_id"],
            ["sales_opportunities.id", "sales_opportunities.store_id", "sales_opportunities.customer_id"],
            name="fk_reminder_opportunity_scope",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    message_template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("message_templates.id", ondelete="RESTRICT"), nullable=False
    )
    product_interest: Mapped[str] = mapped_column(String(200), nullable=False)
    product_key: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rendered_message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    execution_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    claim_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    provider_status: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_transport_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class SalesOpportunity(Base):
    __tablename__ = "sales_opportunities"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'won', 'lost')", name="ck_sales_opportunity_status"),
        ForeignKeyConstraint(
            ["customer_id", "store_id"],
            ["customers.id", "customers.store_id"],
            name="fk_sales_opportunity_customer_store",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("id", "store_id", "customer_id", name="uq_sales_opportunity_identity"),
        Index(
            "uq_open_sales_opportunity",
            "store_id",
            "customer_id",
            "product_key",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("ix_sales_opportunities_store_status_created", "store_id", "status", "created_at"),
        Index("ix_sales_opportunities_store_closed", "store_id", "closed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    lost_reason: Mapped[str | None] = mapped_column(String(500))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    customer = relationship("Customer")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    closed_by = relationship("User", foreign_keys=[closed_by_user_id])
    events = relationship(
        "SalesOpportunityEvent",
        back_populates="opportunity",
        cascade="all, delete-orphan",
        order_by="SalesOpportunityEvent.occurred_at",
    )


class SalesOpportunityEvent(Base):
    __tablename__ = "sales_opportunity_events"
    __table_args__ = (
        CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('open', 'won', 'lost')",
            name="ck_sales_opportunity_event_previous_status",
        ),
        CheckConstraint("new_status IN ('open', 'won', 'lost')", name="ck_sales_opportunity_event_new_status"),
        Index("ix_sales_opportunity_events_opportunity_time", "opportunity_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sales_opportunities.id", ondelete="CASCADE"), nullable=False
    )
    previous_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16), nullable=False)
    performed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    lost_reason: Mapped[str | None] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    opportunity = relationship("SalesOpportunity", back_populates="events")
    performed_by = relationship("User")


class WhatsMiauConfiguration(Base):
    __tablename__ = "whatsmiau_configurations"
    __table_args__ = (
        UniqueConstraint("store_id", name="uq_whatsmiau_configuration_store"),
        Index("ix_whatsmiau_configuration_enabled", "is_enabled", "dispatch_paused"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    instance_name: Mapped[str] = mapped_column(String(40), nullable=False)
    credential_env_var: Mapped[str] = mapped_column(String(128), nullable=False)
    webhook_secret_env_var: Mapped[str | None] = mapped_column(String(128))
    homologation_phone_e164: Mapped[str | None] = mapped_column(String(16))
    homologation_authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dispatch_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connection_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_connection_error: Mapped[str | None] = mapped_column(String(255))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReminderDeliveryAttempt(Base):
    __tablename__ = "reminder_delivery_attempts"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'accepted', 'retry_wait', 'uncertain', "
            "'failed', 'skipped', 'disconnected')",
            name="ck_reminder_delivery_attempt_status",
        ),
        UniqueConstraint("reminder_id", "attempt_number", name="uq_attempt_reminder_number"),
        Index("ix_delivery_attempts_store_started", "store_id", "started_at"),
        Index("ix_delivery_attempts_status", "status", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reminder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reminders.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="RESTRICT"), nullable=False
    )
    configuration_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsmiau_configurations.id", ondelete="SET NULL"),
    )
    attempt_number: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    provider_status: Mapped[str | None] = mapped_column(String(64))
    error_category: Mapped[str | None] = mapped_column(String(32))
    sanitized_error: Mapped[str | None] = mapped_column(String(500))
    http_status: Mapped[int | None] = mapped_column()
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
