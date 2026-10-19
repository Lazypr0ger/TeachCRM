from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BillingMode:
    PER_LESSON = "PER_LESSON"
    MONTHLY = "MONTHLY"


class BillingProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_profiles"
    __table_args__ = (
        CheckConstraint(
            "billing_mode IN ('PER_LESSON', 'MONTHLY')", name="ck_billing_profile_mode"
        ),
        CheckConstraint("price_per_lesson >= 0", name="ck_billing_profile_price"),
        CheckConstraint("currency = 'RUB'", name="ck_billing_profile_currency"),
        CheckConstraint(
            "(billing_mode = 'MONTHLY' AND monthly_due_day BETWEEN 1 AND 31) "
            "OR (billing_mode = 'PER_LESSON' AND monthly_due_day IS NULL)",
            name="ck_billing_profile_due_day",
        ),
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    billing_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    price_per_lesson: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="RUB", nullable=False)
    family_discount_enabled: Mapped[bool] = mapped_column(Boolean(), default=False, nullable=False)
    monthly_due_day: Mapped[int | None]
    monthly_settlement_rule: Mapped[str] = mapped_column(
        String(32), default="PREPAY_SCHEDULED", nullable=False
    )
    updated_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
