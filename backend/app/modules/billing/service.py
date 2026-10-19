from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit
from app.modules.billing.models import BillingMode, BillingProfile
from app.modules.billing.schemas import BillingProfileResponse, BillingProfileUpdateRequest

MONEY_QUANT = Decimal("0.01")


class BillingProfileNotFoundError(Exception):
    pass


class BillingProfileConflictError(Exception):
    pass


def money_round(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def effective_discount(mode: str, family_discount_enabled: bool) -> Decimal:
    discounts: list[Decimal] = []
    if family_discount_enabled:
        discounts.append(Decimal("0.20"))
    if mode == BillingMode.MONTHLY:
        discounts.append(Decimal("0.10"))
    return max(discounts, default=Decimal("0"))


def discounted_amount(base_amount: Decimal, discount: Decimal) -> Decimal:
    return money_round(base_amount * (Decimal("1") - discount))


def profile_response(item: BillingProfile) -> BillingProfileResponse:
    discount = effective_discount(item.billing_mode, item.family_discount_enabled)
    return BillingProfileResponse(
        id=item.id,
        student_id=item.student_id,
        billing_mode=item.billing_mode,
        price_per_lesson=item.price_per_lesson,
        currency=item.currency,
        family_discount_enabled=item.family_discount_enabled,
        monthly_due_day=item.monthly_due_day,
        monthly_settlement_rule=item.monthly_settlement_rule,
        effective_discount_percent=discount * 100,
        effective_price_per_lesson=discounted_amount(item.price_per_lesson, discount),
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def ensure_student(db: Session, student_id: UUID) -> None:
    if db.get(StudentProfile, student_id) is None:
        raise BillingProfileNotFoundError("Ученик не найден")


def get_billing_profile(db: Session, student_id: UUID) -> BillingProfileResponse:
    ensure_student(db, student_id)
    item = db.scalar(select(BillingProfile).where(BillingProfile.student_id == student_id))
    if item is None:
        raise BillingProfileNotFoundError("Финансовый профиль ещё не настроен")
    return profile_response(item)


def upsert_billing_profile(
    db: Session,
    student_id: UUID,
    payload: BillingProfileUpdateRequest,
    teacher: User,
) -> BillingProfileResponse:
    ensure_student(db, student_id)
    item = db.scalar(
        select(BillingProfile).where(BillingProfile.student_id == student_id).with_for_update()
    )
    if item is None:
        if payload.version is not None:
            raise BillingProfileConflictError("Финансовый профиль ещё не создан")
        item = BillingProfile(
            student_id=student_id,
            billing_mode=payload.billing_mode,
            price_per_lesson=money_round(payload.price_per_lesson),
            currency="RUB",
            family_discount_enabled=payload.family_discount_enabled,
            monthly_due_day=payload.monthly_due_day,
            monthly_settlement_rule="PREPAY_SCHEDULED",
            updated_by_user_id=teacher.id,
            version=1,
        )
        db.add(item)
        action = "BILLING_PROFILE_CREATED"
    else:
        if payload.version != item.version:
            raise BillingProfileConflictError("Финансовый профиль уже был изменён")
        item.billing_mode = payload.billing_mode
        item.price_per_lesson = money_round(payload.price_per_lesson)
        item.family_discount_enabled = payload.family_discount_enabled
        item.monthly_due_day = payload.monthly_due_day
        item.updated_by_user_id = teacher.id
        item.version += 1
        action = "BILLING_PROFILE_UPDATED"
    db.flush()
    add_audit(db, teacher.id, action, "billing_profile", item.id)
    db.commit()
    db.refresh(item)
    return profile_response(item)
