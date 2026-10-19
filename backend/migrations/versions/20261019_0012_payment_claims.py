"""Add manual payment claims, confirmed payments and allocations."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0012"
down_revision = "20261019_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_claims",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "submitted_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("declared_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("comment", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("decided_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("declared_amount > 0", name="ck_payment_claim_amount"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'REJECTED')", name="ck_payment_claim_status"
        ),
    )
    op.create_index("ix_payment_claims_invoice_id", "payment_claims", ["invoice_id"])
    op.create_index(
        "uq_payment_claim_pending_invoice",
        "payment_claims",
        ["invoice_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
        sqlite_where=sa.text("status = 'PENDING'"),
    )
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "claim_id",
            sa.Uuid(),
            sa.ForeignKey("payment_claims.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column(
            "confirmed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_payment_amount"),
    )
    op.create_index("ix_payments_student_id", "payments", ["student_id"])
    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "payment_id",
            sa.Uuid(),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "invoice_id",
            sa.Uuid(),
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_target"),
        sa.CheckConstraint("amount > 0", name="ck_payment_allocation_amount"),
    )
    op.create_index("ix_payment_allocations_invoice_id", "payment_allocations", ["invoice_id"])


def downgrade() -> None:
    op.drop_table("payment_allocations")
    op.drop_table("payments")
    op.drop_table("payment_claims")
