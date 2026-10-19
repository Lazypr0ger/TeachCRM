import calendar
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit, expired, utc_now
from app.modules.billing.models import (
    BillingMode,
    BillingProfile,
    Invoice,
    InvoiceItem,
    Payment,
    PaymentAllocation,
    PaymentClaim,
)
from app.modules.billing.schemas import (
    BillingProfileResponse,
    BillingProfileUpdateRequest,
    BillingSummaryResponse,
    InvoiceAdjustmentRequest,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    PaymentClaimConfirmRequest,
    PaymentClaimCreateRequest,
    PaymentClaimRejectRequest,
    PaymentClaimResponse,
    PaymentResponse,
    PaymentReverseRequest,
)
from app.modules.lessons.models import Lesson, LessonStatus

MONEY_QUANT = Decimal("0.01")


class BillingProfileNotFoundError(Exception):
    pass


class BillingProfileConflictError(Exception):
    pass


class InvoiceValidationError(Exception):
    pass


class InvoiceNotFoundError(Exception):
    pass


class PaymentClaimConflictError(Exception):
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


def invoice_response(db: Session, item: Invoice) -> InvoiceResponse:
    lines = db.scalars(
        select(InvoiceItem)
        .where(InvoiceItem.invoice_id == item.id)
        .order_by(InvoiceItem.created_at, InvoiceItem.id)
    ).all()
    allocated = money_round(
        db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                PaymentAllocation.invoice_id == item.id
            )
        )
        or Decimal("0")
    )
    outstanding = money_round(item.total - allocated)
    pending_claim_id = db.scalar(
        select(PaymentClaim.id).where(
            PaymentClaim.invoice_id == item.id,
            PaymentClaim.status == "PENDING",
        )
    )
    if outstanding == 0:
        status = "PAID"
    elif expired(item.due_at, utc_now()):
        status = "OVERDUE"
    elif allocated > 0:
        status = "PARTIALLY_PAID"
    else:
        status = "UNPAID"
    return InvoiceResponse(
        id=item.id,
        student_id=item.student_id,
        billing_mode_snapshot=item.billing_mode_snapshot,
        period_start=item.period_start.isoformat() if item.period_start else None,
        period_end=item.period_end.isoformat() if item.period_end else None,
        issued_at=item.issued_at,
        due_at=item.due_at,
        currency=item.currency,
        subtotal=item.subtotal,
        discount_percent=item.discount_percent,
        discount_amount=item.discount_amount,
        total=item.total,
        allocated_total=allocated,
        outstanding=outstanding,
        status=status,
        can_submit_claim=outstanding > 0 and pending_claim_id is None,
        pending_claim_id=pending_claim_id,
        items=[
            InvoiceItemResponse(
                id=line.id,
                lesson_id=line.lesson_id,
                kind=line.kind,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                subtotal=line.subtotal,
            )
            for line in lines
        ],
    )


def create_per_lesson_invoice(db: Session, lesson: Lesson, actor: User) -> Invoice | None:
    existing = db.scalar(
        select(Invoice)
        .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
        .where(InvoiceItem.lesson_id == lesson.id, InvoiceItem.kind == "LESSON")
    )
    if existing is not None:
        return None
    profile = db.scalar(
        select(BillingProfile).where(BillingProfile.student_id == lesson.student_id)
    )
    if (
        profile is None
        or profile.billing_mode != BillingMode.PER_LESSON
        or profile.price_per_lesson == 0
        or lesson.completed_at is None
    ):
        return None
    now = utc_now()
    subtotal = money_round(profile.price_per_lesson)
    discount = effective_discount(profile.billing_mode, profile.family_discount_enabled)
    total = discounted_amount(subtotal, discount)
    invoice = Invoice(
        student_id=lesson.student_id,
        billing_mode_snapshot=profile.billing_mode,
        period_start=None,
        period_end=None,
        issued_at=now,
        due_at=lesson.completed_at + timedelta(hours=48),
        currency=profile.currency,
        subtotal=subtotal,
        discount_percent=discount * 100,
        discount_amount=money_round(subtotal - total),
        total=total,
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceItem(
            invoice_id=invoice.id,
            lesson_id=lesson.id,
            kind="LESSON",
            description=f"Проведённый урок: {lesson.title}",
            quantity=Decimal("1.00"),
            unit_price=subtotal,
            subtotal=subtotal,
            created_at=now,
        )
    )
    add_audit(db, actor.id, "INVOICE_CREATED", "invoice", invoice.id)
    return invoice


def list_invoices(db: Session, *, student_id: UUID | None = None) -> InvoiceListResponse:
    query = select(Invoice)
    count_query = select(func.count()).select_from(Invoice)
    if student_id is not None:
        query = query.where(Invoice.student_id == student_id)
        count_query = count_query.where(Invoice.student_id == student_id)
    items = db.scalars(query.order_by(Invoice.issued_at.desc(), Invoice.id)).all()
    return InvoiceListResponse(
        items=[invoice_response(db, item) for item in items],
        total=db.scalar(count_query) or 0,
    )


def student_billing_summary(db: Session, user: User) -> BillingSummaryResponse:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if profile is None:
        raise BillingProfileNotFoundError("Ученик не найден")
    billing = db.scalar(select(BillingProfile).where(BillingProfile.student_id == profile.id))
    invoices = list_invoices(db, student_id=profile.id).items
    received = money_round(
        db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.student_id == profile.id
            )
        )
        or Decimal("0")
    )
    return BillingSummaryResponse(
        profile=profile_response(billing) if billing else None,
        accrued_total=money_round(sum((item.total for item in invoices), Decimal("0"))),
        received_total=received,
        outstanding_total=money_round(sum((item.outstanding for item in invoices), Decimal("0"))),
        overdue_total=money_round(
            sum((item.outstanding for item in invoices if item.status == "OVERDUE"), Decimal("0"))
        ),
        discount_total=money_round(sum((item.discount_amount for item in invoices), Decimal("0"))),
    )


def finance_summary(db: Session, *, student_id: UUID | None = None) -> BillingSummaryResponse:
    invoices = list_invoices(db, student_id=student_id).items
    payment_query = select(func.coalesce(func.sum(Payment.amount), 0))
    if student_id is not None:
        payment_query = payment_query.where(Payment.student_id == student_id)
    received = money_round(db.scalar(payment_query) or Decimal("0"))
    return BillingSummaryResponse(
        profile=None,
        accrued_total=money_round(sum((item.total for item in invoices), Decimal("0"))),
        received_total=received,
        outstanding_total=money_round(sum((item.outstanding for item in invoices), Decimal("0"))),
        overdue_total=money_round(
            sum((item.outstanding for item in invoices if item.status == "OVERDUE"), Decimal("0"))
        ),
        discount_total=money_round(sum((item.discount_amount for item in invoices), Decimal("0"))),
    )


def monthly_period(year: int, month: int, timezone: str) -> tuple[date, date, datetime, datetime]:
    last_day = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)
    zone = ZoneInfo(timezone)
    start_at = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(UTC)
    next_month = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    end_at = datetime.combine(next_month, time.min, tzinfo=zone).astimezone(UTC)
    return start_date, end_date, start_at, end_at


def create_monthly_invoice(
    db: Session, *, student_id: UUID, year: int, month: int, actor: User, timezone: str
) -> InvoiceResponse:
    profile = db.scalar(
        select(BillingProfile).where(BillingProfile.student_id == student_id).with_for_update()
    )
    if profile is None:
        raise BillingProfileNotFoundError("Финансовый профиль ещё не настроен")
    if profile.billing_mode != BillingMode.MONTHLY or profile.monthly_due_day is None:
        raise InvoiceValidationError("У ученика не настроена помесячная оплата")
    period_start, period_end, starts_at, ends_at = monthly_period(year, month, timezone)
    existing = db.scalar(
        select(Invoice).where(
            Invoice.student_id == student_id,
            Invoice.billing_mode_snapshot == BillingMode.MONTHLY,
            Invoice.period_start == period_start,
        )
    )
    if existing is not None:
        return invoice_response(db, existing)
    already_charged = select(InvoiceItem.lesson_id).where(InvoiceItem.lesson_id.is_not(None))
    lessons = db.scalars(
        select(Lesson)
        .where(
            Lesson.student_id == student_id,
            Lesson.status != LessonStatus.CANCELLED,
            Lesson.starts_at >= starts_at,
            Lesson.starts_at < ends_at,
            Lesson.id.not_in(already_charged),
        )
        .order_by(Lesson.starts_at, Lesson.id)
    ).all()
    if not lessons or profile.price_per_lesson == 0:
        raise InvoiceValidationError("В выбранном месяце нет оплачиваемых занятий")
    subtotal = money_round(profile.price_per_lesson * len(lessons))
    discount = effective_discount(profile.billing_mode, profile.family_discount_enabled)
    total = discounted_amount(subtotal, discount)
    zone = ZoneInfo(timezone)
    due_day = min(profile.monthly_due_day, period_end.day)
    due_at = datetime.combine(date(year, month, due_day), time(23, 59), tzinfo=zone).astimezone(UTC)
    now = utc_now()
    invoice = Invoice(
        student_id=student_id,
        billing_mode_snapshot=BillingMode.MONTHLY,
        period_start=period_start,
        period_end=period_end,
        issued_at=now,
        due_at=due_at,
        currency=profile.currency,
        subtotal=subtotal,
        discount_percent=discount * 100,
        discount_amount=money_round(subtotal - total),
        total=total,
    )
    db.add(invoice)
    db.flush()
    for lesson in lessons:
        db.add(
            InvoiceItem(
                invoice_id=invoice.id,
                lesson_id=lesson.id,
                kind="LESSON",
                description=f"Запланированный урок: {lesson.title}",
                quantity=Decimal("1.00"),
                unit_price=profile.price_per_lesson,
                subtotal=profile.price_per_lesson,
                created_at=now,
            )
        )
    add_audit(db, actor.id, "MONTHLY_INVOICE_CREATED", "invoice", invoice.id)
    db.commit()
    db.refresh(invoice)
    return invoice_response(db, invoice)


def add_invoice_adjustment(
    db: Session, invoice_id: UUID, payload: InvoiceAdjustmentRequest, actor: User
) -> InvoiceResponse:
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update())
    if invoice is None:
        raise InvoiceNotFoundError("Начисление не найдено")
    if db.scalar(
        select(PaymentClaim.id).where(
            PaymentClaim.invoice_id == invoice.id,
            PaymentClaim.status == "PENDING",
        )
    ):
        raise InvoiceValidationError("Сначала обработайте ожидающее заявление об оплате")
    amount = money_round(payload.amount)
    new_subtotal = money_round(invoice.subtotal + amount)
    if new_subtotal < 0:
        raise InvoiceValidationError("Корректировка делает начисление отрицательным")
    discount = invoice.discount_percent / 100
    new_total = discounted_amount(new_subtotal, discount)
    allocated = money_round(
        db.scalar(
            select(func.coalesce(func.sum(PaymentAllocation.amount), 0)).where(
                PaymentAllocation.invoice_id == invoice.id
            )
        )
        or Decimal("0")
    )
    if new_total < allocated:
        raise InvoiceValidationError("Итог не может быть меньше подтверждённых платежей")
    invoice.subtotal = new_subtotal
    invoice.discount_amount = money_round(new_subtotal - new_total)
    invoice.total = new_total
    db.add(
        InvoiceItem(
            invoice_id=invoice.id,
            lesson_id=None,
            kind="ADJUSTMENT",
            description=f"Корректировка: {payload.reason}",
            quantity=Decimal("1.00"),
            unit_price=amount,
            subtotal=amount,
            created_at=utc_now(),
        )
    )
    add_audit(db, actor.id, "INVOICE_ADJUSTED", "invoice", invoice.id)
    db.commit()
    db.refresh(invoice)
    return invoice_response(db, invoice)


def payment_response(item: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=item.id,
        student_id=item.student_id,
        claim_id=item.claim_id,
        amount=item.amount,
        received_at=item.received_at,
        reversal_of_payment_id=item.reversal_of_payment_id,
        reversal_reason=item.reversal_reason,
        created_at=item.created_at,
    )


def claim_response(db: Session, item: PaymentClaim) -> PaymentClaimResponse:
    invoice = db.get(Invoice, item.invoice_id)
    profile = db.get(StudentProfile, invoice.student_id) if invoice else None
    if invoice is None or profile is None:
        raise InvoiceNotFoundError("Начисление не найдено")
    student_name = " ".join(
        part for part in (profile.last_name, profile.first_name, profile.patronymic) if part
    )
    return PaymentClaimResponse(
        id=item.id,
        invoice_id=item.invoice_id,
        student_id=profile.id,
        student_name=student_name,
        declared_amount=item.declared_amount,
        paid_at=item.paid_at,
        comment=item.comment,
        status=item.status,
        rejection_reason=item.rejection_reason,
        decided_at=item.decided_at,
        created_at=item.created_at,
    )


def create_payment_claim(
    db: Session, invoice_id: UUID, payload: PaymentClaimCreateRequest, student: User
) -> PaymentClaimResponse:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == student.id))
    invoice = db.scalar(select(Invoice).where(Invoice.id == invoice_id).with_for_update())
    if profile is None or invoice is None or invoice.student_id != profile.id:
        raise InvoiceNotFoundError("Начисление не найдено")
    snapshot = invoice_response(db, invoice)
    if snapshot.outstanding <= 0:
        raise PaymentClaimConflictError("Начисление уже оплачено")
    if snapshot.pending_claim_id is not None:
        raise PaymentClaimConflictError("Заявление уже ожидает решения")
    amount = money_round(payload.declared_amount)
    if amount > snapshot.outstanding:
        raise InvoiceValidationError("Заявленная сумма превышает остаток начисления")
    item = PaymentClaim(
        invoice_id=invoice.id,
        submitted_by_user_id=student.id,
        declared_amount=amount,
        paid_at=payload.paid_at,
        comment=payload.comment.strip() if payload.comment else None,
        status="PENDING",
        rejection_reason=None,
        decided_by_user_id=None,
        decided_at=None,
    )
    db.add(item)
    try:
        db.flush()
        add_audit(db, student.id, "PAYMENT_CLAIM_CREATED", "payment_claim", item.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PaymentClaimConflictError("Заявление уже ожидает решения") from exc
    db.refresh(item)
    return claim_response(db, item)


def list_payment_claims(
    db: Session, *, student_user_id: UUID | None = None, claim_status: str | None = None
) -> list[PaymentClaimResponse]:
    query = select(PaymentClaim)
    if student_user_id is not None:
        query = query.where(PaymentClaim.submitted_by_user_id == student_user_id)
    if claim_status is not None:
        query = query.where(PaymentClaim.status == claim_status)
    items = db.scalars(query.order_by(PaymentClaim.created_at.desc(), PaymentClaim.id)).all()
    return [claim_response(db, item) for item in items]


def confirm_payment_claim(
    db: Session, claim_id: UUID, payload: PaymentClaimConfirmRequest, teacher: User
) -> PaymentResponse:
    existing_by_key = db.scalar(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    )
    if existing_by_key is not None:
        if existing_by_key.claim_id == claim_id:
            return payment_response(existing_by_key)
        raise PaymentClaimConflictError("Идентификатор подтверждения уже использован")
    claim = db.scalar(select(PaymentClaim).where(PaymentClaim.id == claim_id).with_for_update())
    if claim is None:
        raise InvoiceNotFoundError("Заявление не найдено")
    invoice = db.scalar(select(Invoice).where(Invoice.id == claim.invoice_id).with_for_update())
    if invoice is None:
        raise InvoiceNotFoundError("Начисление не найдено")
    if claim.status != "PENDING":
        raise PaymentClaimConflictError("Заявление уже обработано")
    snapshot = invoice_response(db, invoice)
    amount = money_round(payload.confirmed_amount)
    if amount > snapshot.outstanding:
        raise InvoiceValidationError("Подтверждённая сумма превышает остаток начисления")
    now = utc_now()
    payment = Payment(
        student_id=invoice.student_id,
        claim_id=claim.id,
        confirmed_by_user_id=teacher.id,
        amount=amount,
        received_at=payload.received_at,
        idempotency_key=payload.idempotency_key,
        reversal_of_payment_id=None,
        reversal_reason=None,
        created_at=now,
    )
    db.add(payment)
    db.flush()
    db.add(
        PaymentAllocation(
            payment_id=payment.id,
            invoice_id=invoice.id,
            amount=amount,
            created_at=now,
        )
    )
    claim.status = "CONFIRMED"
    claim.decided_by_user_id = teacher.id
    claim.decided_at = now
    add_audit(db, teacher.id, "PAYMENT_CLAIM_CONFIRMED", "payment_claim", claim.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
        )
        if existing is not None and existing.claim_id == claim_id:
            return payment_response(existing)
        raise PaymentClaimConflictError("Заявление уже обработано") from exc
    db.refresh(payment)
    return payment_response(payment)


def reject_payment_claim(
    db: Session, claim_id: UUID, payload: PaymentClaimRejectRequest, teacher: User
) -> PaymentClaimResponse:
    claim = db.scalar(select(PaymentClaim).where(PaymentClaim.id == claim_id).with_for_update())
    if claim is None:
        raise InvoiceNotFoundError("Заявление не найдено")
    if claim.status != "PENDING":
        raise PaymentClaimConflictError("Заявление уже обработано")
    claim.status = "REJECTED"
    claim.rejection_reason = payload.reason.strip() if payload.reason else None
    claim.decided_by_user_id = teacher.id
    claim.decided_at = utc_now()
    add_audit(db, teacher.id, "PAYMENT_CLAIM_REJECTED", "payment_claim", claim.id)
    db.commit()
    db.refresh(claim)
    return claim_response(db, claim)


def list_payments(db: Session, *, student_id: UUID | None = None) -> list[PaymentResponse]:
    query = select(Payment)
    if student_id is not None:
        query = query.where(Payment.student_id == student_id)
    items = db.scalars(query.order_by(Payment.received_at.desc(), Payment.id)).all()
    return [payment_response(item) for item in items]


def reverse_payment(
    db: Session, payment_id: UUID, payload: PaymentReverseRequest, teacher: User
) -> PaymentResponse:
    existing_by_key = db.scalar(
        select(Payment).where(Payment.idempotency_key == payload.idempotency_key)
    )
    if existing_by_key is not None:
        if existing_by_key.reversal_of_payment_id == payment_id:
            return payment_response(existing_by_key)
        raise PaymentClaimConflictError("Идентификатор операции уже использован")
    original = db.scalar(select(Payment).where(Payment.id == payment_id).with_for_update())
    if original is None:
        raise InvoiceNotFoundError("Платёж не найден")
    if original.reversal_of_payment_id is not None:
        raise PaymentClaimConflictError("Обратную операцию нельзя отменить повторно")
    if (
        db.scalar(select(Payment.id).where(Payment.reversal_of_payment_id == original.id))
        is not None
    ):
        raise PaymentClaimConflictError("Платёж уже исправлен обратной операцией")
    allocation = db.scalar(
        select(PaymentAllocation)
        .where(PaymentAllocation.payment_id == original.id)
        .with_for_update()
    )
    if allocation is None:
        raise InvoiceNotFoundError("Распределение платежа не найдено")
    now = utc_now()
    reversal = Payment(
        student_id=original.student_id,
        claim_id=None,
        confirmed_by_user_id=teacher.id,
        amount=-original.amount,
        received_at=payload.reversed_at,
        idempotency_key=payload.idempotency_key,
        reversal_of_payment_id=original.id,
        reversal_reason=payload.reason.strip(),
        created_at=now,
    )
    db.add(reversal)
    db.flush()
    db.add(
        PaymentAllocation(
            payment_id=reversal.id,
            invoice_id=allocation.invoice_id,
            amount=-allocation.amount,
            created_at=now,
        )
    )
    add_audit(db, teacher.id, "PAYMENT_REVERSED", "payment", original.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(select(Payment).where(Payment.reversal_of_payment_id == payment_id))
        if existing is not None and existing.idempotency_key == payload.idempotency_key:
            return payment_response(existing)
        raise PaymentClaimConflictError("Платёж уже исправлен") from exc
    db.refresh(reversal)
    return payment_response(reversal)
