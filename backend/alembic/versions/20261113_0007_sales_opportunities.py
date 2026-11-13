"""Add sales opportunities, audit events, and reminder association.

Revision ID: 20261113_0007
Revises: 20261107_0006
Create Date: 2026-11-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261113_0007"
down_revision: str | None = "20261107_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_customers_id_store", "customers", ["id", "store_id"])
    op.create_table(
        "sales_opportunities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(length=200), nullable=False),
        sa.Column("product_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("closed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('open', 'won', 'lost')", name="ck_sales_opportunity_status"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["customer_id", "store_id"],
            ["customers.id", "customers.store_id"],
            name="fk_sales_opportunity_customer_store",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["closed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "store_id", "customer_id", name="uq_sales_opportunity_identity"),
    )
    op.create_index(
        "uq_open_sales_opportunity",
        "sales_opportunities",
        ["store_id", "customer_id", "product_key"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_index(
        "ix_sales_opportunities_store_status_created",
        "sales_opportunities",
        ["store_id", "status", "created_at"],
    )
    op.create_index(
        "ix_sales_opportunities_store_closed", "sales_opportunities", ["store_id", "closed_at"]
    )
    op.create_table(
        "sales_opportunity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("previous_status", sa.String(length=16), nullable=True),
        sa.Column("new_status", sa.String(length=16), nullable=False),
        sa.Column("performed_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lost_reason", sa.String(length=500), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status IN ('open', 'won', 'lost')",
            name="ck_sales_opportunity_event_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IN ('open', 'won', 'lost')",
            name="ck_sales_opportunity_event_new_status",
        ),
        sa.ForeignKeyConstraint(["opportunity_id"], ["sales_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sales_opportunity_events_opportunity_time",
        "sales_opportunity_events",
        ["opportunity_id", "occurred_at"],
    )
    op.add_column("reminders", sa.Column("opportunity_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_reminder_opportunity_scope",
        "reminders",
        "sales_opportunities",
        ["opportunity_id", "store_id", "customer_id"],
        ["id", "store_id", "customer_id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_reminders_opportunity", "reminders", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_opportunity", table_name="reminders")
    op.drop_constraint("fk_reminder_opportunity_scope", "reminders", type_="foreignkey")
    op.drop_column("reminders", "opportunity_id")
    op.drop_index("ix_sales_opportunity_events_opportunity_time", table_name="sales_opportunity_events")
    op.drop_table("sales_opportunity_events")
    op.drop_index("ix_sales_opportunities_store_closed", table_name="sales_opportunities")
    op.drop_index("ix_sales_opportunities_store_status_created", table_name="sales_opportunities")
    op.drop_index("uq_open_sales_opportunity", table_name="sales_opportunities")
    op.drop_table("sales_opportunities")
    op.drop_constraint("uq_customers_id_store", "customers", type_="unique")
