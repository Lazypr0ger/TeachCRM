from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
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


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        CheckConstraint(
            "billing_mode_snapshot IN ('PER_LESSON', 'MONTHLY')", name="ck_invoice_mode"
        ),
        CheckConstraint("currency = 'RUB'", name="ck_invoice_currency"),
        CheckConstraint(
            "subtotal >= 0 AND discount_amount >= 0 AND total >= 0", name="ck_invoice_amounts"
        ),
        CheckConstraint("discount_percent BETWEEN 0 AND 100", name="ck_invoice_discount"),
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    billing_mode_snapshot: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[date | None] = mapped_column(Date())
    period_end: Mapped[date | None] = mapped_column(Date())
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class InvoiceItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "invoice_items"
    __table_args__ = (
        CheckConstraint("kind IN ('LESSON', 'ADJUSTMENT')", name="ck_invoice_item_kind"),
        CheckConstraint("quantity > 0", name="ck_invoice_item_quantity"),
        UniqueConstraint("lesson_id", "kind", name="uq_invoice_item_lesson_kind"),
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    lesson_id: Mapped[UUID | None] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_claims"
    __table_args__ = (
        CheckConstraint("declared_amount > 0", name="ck_payment_claim_amount"),
        CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'REJECTED')", name="ck_payment_claim_status"
        ),
    )

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submitted_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    declared_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text())
    decided_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount"),)

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    claim_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_claims.id", ondelete="RESTRICT"), unique=True
    )
    confirmed_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaymentAllocation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "payment_allocations"
    __table_args__ = (
        UniqueConstraint("payment_id", "invoice_id", name="uq_payment_allocation_target"),
        CheckConstraint("amount > 0", name="ck_payment_allocation_amount"),
    )

    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
