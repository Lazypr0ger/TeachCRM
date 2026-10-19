"""Add immutable invoices and invoice items."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0010"
down_revision = "20261019_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("billing_mode_snapshot", sa.String(16), nullable=False),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "billing_mode_snapshot IN ('PER_LESSON', 'MONTHLY')", name="ck_invoice_mode"
        ),
        sa.CheckConstraint("currency = 'RUB'", name="ck_invoice_currency"),
        sa.CheckConstraint(
            "subtotal >= 0 AND discount_amount >= 0 AND total >= 0", name="ck_invoice_amounts"
        ),
        sa.CheckConstraint("discount_percent BETWEEN 0 AND 100", name="ck_invoice_discount"),
    )
    op.create_index("ix_invoices_student_id", "invoices", ["student_id"])
    op.create_table(
        "invoice_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("lesson_id", sa.Uuid(), sa.ForeignKey("lessons.id", ondelete="RESTRICT")),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('LESSON', 'ADJUSTMENT')", name="ck_invoice_item_kind"),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_item_quantity"),
        sa.UniqueConstraint("lesson_id", "kind", name="uq_invoice_item_lesson_kind"),
    )
    op.create_index("ix_invoice_items_invoice_id", "invoice_items", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("invoice_items")
    op.drop_table("invoices")
