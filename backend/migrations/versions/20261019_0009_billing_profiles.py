"""Add student billing profiles."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0009"
down_revision = "20261019_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("billing_mode", sa.String(16), nullable=False),
        sa.Column("price_per_lesson", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="RUB"),
        sa.Column(
            "family_discount_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("monthly_due_day", sa.SmallInteger()),
        sa.Column(
            "monthly_settlement_rule",
            sa.String(32),
            nullable=False,
            server_default="PREPAY_SCHEDULED",
        ),
        sa.Column(
            "updated_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "billing_mode IN ('PER_LESSON', 'MONTHLY')", name="ck_billing_profile_mode"
        ),
        sa.CheckConstraint("price_per_lesson >= 0", name="ck_billing_profile_price"),
        sa.CheckConstraint("currency = 'RUB'", name="ck_billing_profile_currency"),
        sa.CheckConstraint(
            "(billing_mode = 'MONTHLY' AND monthly_due_day BETWEEN 1 AND 31) "
            "OR (billing_mode = 'PER_LESSON' AND monthly_due_day IS NULL)",
            name="ck_billing_profile_due_day",
        ),
    )


def downgrade() -> None:
    op.drop_table("billing_profiles")
