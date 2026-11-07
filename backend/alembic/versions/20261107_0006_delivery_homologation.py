"""Add delivery confirmations and homologation controls.

Revision ID: 20261107_0006
Revises: 20261106_0005
Create Date: 2026-11-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20261107_0006"
down_revision: str | None = "20261106_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "whatsmiau_configurations",
        sa.Column("webhook_secret_env_var", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "whatsmiau_configurations",
        sa.Column("homologation_phone_e164", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "whatsmiau_configurations",
        sa.Column("homologation_authorized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("reminders", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.add_column("reminders", sa.Column("read_at", sa.DateTime(timezone=True)))
    op.add_column(
        "reminder_delivery_attempts",
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "reminder_delivery_attempts", sa.Column("read_at", sa.DateTime(timezone=True))
    )


def downgrade() -> None:
    op.drop_column("reminder_delivery_attempts", "read_at")
    op.drop_column("reminder_delivery_attempts", "delivered_at")
    op.drop_column("reminders", "read_at")
    op.drop_column("reminders", "delivered_at")
    op.drop_column("whatsmiau_configurations", "homologation_authorized_at")
    op.drop_column("whatsmiau_configurations", "homologation_phone_e164")
    op.drop_column("whatsmiau_configurations", "webhook_secret_env_var")
