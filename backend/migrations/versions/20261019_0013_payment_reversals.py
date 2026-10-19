"""Add auditable payment reversal operations."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0013"
down_revision = "20261019_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_payment_amount", "payments", type_="check")
    op.create_check_constraint("ck_payment_amount", "payments", "amount != 0")
    op.add_column("payments", sa.Column("reversal_of_payment_id", sa.Uuid()))
    op.add_column("payments", sa.Column("reversal_reason", sa.Text()))
    op.create_foreign_key(
        "fk_payment_reversal_original",
        "payments",
        "payments",
        ["reversal_of_payment_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_payment_reversal_original", "payments", ["reversal_of_payment_id"]
    )
    op.drop_constraint("ck_payment_allocation_amount", "payment_allocations", type_="check")
    op.create_check_constraint("ck_payment_allocation_amount", "payment_allocations", "amount != 0")


def downgrade() -> None:
    op.drop_constraint("ck_payment_allocation_amount", "payment_allocations", type_="check")
    op.create_check_constraint("ck_payment_allocation_amount", "payment_allocations", "amount > 0")
    op.drop_constraint("uq_payment_reversal_original", "payments", type_="unique")
    op.drop_constraint("fk_payment_reversal_original", "payments", type_="foreignkey")
    op.drop_column("payments", "reversal_reason")
    op.drop_column("payments", "reversal_of_payment_id")
    op.drop_constraint("ck_payment_amount", "payments", type_="check")
    op.create_check_constraint("ck_payment_amount", "payments", "amount > 0")
