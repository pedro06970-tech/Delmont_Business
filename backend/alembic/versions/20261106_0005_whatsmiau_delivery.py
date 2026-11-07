"""Add WhatsMiau configuration and reminder delivery state.

Revision ID: 20261106_0005
Revises: 20261106_0004
Create Date: 2026-11-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261106_0005"
down_revision: str | None = "20261106_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "whatsmiau_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instance_name", sa.String(length=40), nullable=False),
        sa.Column("credential_env_var", sa.String(length=128), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("dispatch_paused", sa.Boolean(), nullable=False),
        sa.Column("connection_state", sa.String(length=32), nullable=False),
        sa.Column("last_connection_error", sa.String(length=255), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_dispatch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", name="uq_whatsmiau_configuration_store"),
    )
    op.create_index(
        "ix_whatsmiau_configuration_enabled",
        "whatsmiau_configurations",
        ["is_enabled", "dispatch_paused"],
    )

    op.add_column(
        "reminders",
        sa.Column("execution_status", sa.String(length=16), server_default="pending", nullable=False),
    )
    op.add_column("reminders", sa.Column("claim_token", postgresql.UUID(as_uuid=True)))
    op.add_column("reminders", sa.Column("claimed_at", sa.DateTime(timezone=True)))
    op.add_column("reminders", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("reminders", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.add_column(
        "reminders", sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column("reminders", sa.Column("provider_message_id", sa.String(length=255)))
    op.add_column("reminders", sa.Column("provider_status", sa.String(length=64)))
    op.add_column("reminders", sa.Column("accepted_at", sa.DateTime(timezone=True)))
    op.add_column("reminders", sa.Column("last_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("reminders", sa.Column("last_transport_error", sa.Text()))
    op.create_check_constraint(
        "ck_reminder_execution_status",
        "reminders",
        "execution_status IN ('pending', 'claimed', 'sending', 'sent', "
        "'retry_wait', 'uncertain', 'failed')",
    )
    op.create_index(
        "ix_reminders_execution_due",
        "reminders",
        ["execution_status", "next_attempt_at", "scheduled_for"],
    )

    op.create_table(
        "reminder_delivery_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_status", sa.String(length=64), nullable=True),
        sa.Column("error_category", sa.String(length=32), nullable=True),
        sa.Column("sanitized_error", sa.String(length=500), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('started', 'accepted', 'retry_wait', 'uncertain', "
            "'failed', 'skipped', 'disconnected')",
            name="ck_reminder_delivery_attempt_status",
        ),
        sa.ForeignKeyConstraint(["configuration_id"], ["whatsmiau_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reminder_id"], ["reminders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reminder_id", "attempt_number", name="uq_attempt_reminder_number"),
    )
    op.create_index(
        "ix_delivery_attempts_store_started",
        "reminder_delivery_attempts",
        ["store_id", "started_at"],
    )
    op.create_index(
        "ix_delivery_attempts_status",
        "reminder_delivery_attempts",
        ["status", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_attempts_status", table_name="reminder_delivery_attempts")
    op.drop_index("ix_delivery_attempts_store_started", table_name="reminder_delivery_attempts")
    op.drop_table("reminder_delivery_attempts")
    op.drop_index("ix_reminders_execution_due", table_name="reminders")
    op.drop_constraint("ck_reminder_execution_status", "reminders", type_="check")
    for column in (
        "last_transport_error",
        "last_attempt_at",
        "accepted_at",
        "provider_status",
        "provider_message_id",
        "attempt_count",
        "next_attempt_at",
        "lease_expires_at",
        "claimed_at",
        "claim_token",
        "execution_status",
    ):
        op.drop_column("reminders", column)
    op.drop_index("ix_whatsmiau_configuration_enabled", table_name="whatsmiau_configurations")
    op.drop_table("whatsmiau_configurations")
