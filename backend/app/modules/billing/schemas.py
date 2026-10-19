from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BillingProfileUpdateRequest(BaseModel):
    billing_mode: Literal["PER_LESSON", "MONTHLY"]
    price_per_lesson: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    family_discount_enabled: bool = False
    monthly_due_day: int | None = Field(default=None, ge=1, le=31)
    version: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def due_day_matches_mode(self) -> "BillingProfileUpdateRequest":
        if self.billing_mode == "MONTHLY" and self.monthly_due_day is None:
            raise ValueError("Для помесячной оплаты укажите день платежа")
        if self.billing_mode == "PER_LESSON" and self.monthly_due_day is not None:
            raise ValueError("День платежа используется только для помесячной оплаты")
        return self


class BillingProfileResponse(BaseModel):
    id: UUID
    student_id: UUID
    billing_mode: str
    price_per_lesson: Decimal
    currency: str
    family_discount_enabled: bool
    monthly_due_day: int | None
    monthly_settlement_rule: str
    effective_discount_percent: Decimal
    effective_price_per_lesson: Decimal
    version: int
    created_at: datetime
    updated_at: datetime


class InvoiceItemResponse(BaseModel):
    id: UUID
    lesson_id: UUID | None
    kind: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal


class InvoiceResponse(BaseModel):
    id: UUID
    student_id: UUID
    billing_mode_snapshot: str
    period_start: str | None
    period_end: str | None
    issued_at: datetime
    due_at: datetime
    currency: str
    subtotal: Decimal
    discount_percent: Decimal
    discount_amount: Decimal
    total: Decimal
    allocated_total: Decimal
    outstanding: Decimal
    status: str
    items: list[InvoiceItemResponse]


class InvoiceListResponse(BaseModel):
    items: list[InvoiceResponse]
    total: int


class BillingSummaryResponse(BaseModel):
    profile: BillingProfileResponse | None
    accrued_total: Decimal
    received_total: Decimal
    outstanding_total: Decimal
    overdue_total: Decimal
    discount_total: Decimal
