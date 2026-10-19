"""Guarantee one monthly invoice per student and period."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0011"
down_revision = "20261019_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_invoices_monthly_period",
        "invoices",
        ["student_id", "period_start", "billing_mode_snapshot"],
        unique=True,
        postgresql_where=sa.text("billing_mode_snapshot = 'MONTHLY'"),
        sqlite_where=sa.text("billing_mode_snapshot = 'MONTHLY'"),
    )


def downgrade() -> None:
    op.drop_index("uq_invoices_monthly_period", table_name="invoices")
