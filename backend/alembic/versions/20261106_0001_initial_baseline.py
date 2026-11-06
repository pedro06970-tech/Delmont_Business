"""Create the initial database baseline.

Revision ID: 20261106_0001
Revises:
Create Date: 2026-11-06
"""

from collections.abc import Sequence

revision: str = "20261106_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish an empty baseline for future schema changes."""


def downgrade() -> None:
    """Remove the empty baseline without changing the schema."""
