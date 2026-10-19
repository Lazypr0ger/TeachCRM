from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import utc_now
from app.modules.notifications.models import Notification, OutboxEvent
from app.modules.notifications.schemas import NotificationPage, NotificationResponse


class NotificationNotFoundError(Exception):
    pass


def enqueue_notification(
    db: Session,
    *,
    event_type: str,
    aggregate_id: UUID,
    recipient_user_id: UUID,
    title: str,
    body: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    deduplication_key: str | None = None,
) -> None:
    now = utc_now()
    db.add(
        OutboxEvent(
            event_type=event_type,
            aggregate_id=aggregate_id,
            deduplication_key=deduplication_key,
            payload={
                "recipient_user_id": str(recipient_user_id),
                "title": title,
                "body": body,
                "target_type": target_type,
                "target_id": str(target_id) if target_id else None,
            },
            status="PENDING",
            attempt_count=0,
            next_attempt_at=now,
            sent_at=None,
            last_error=None,
            created_at=now,
        )
    )


def enqueue_payment_due_notifications(db: Session) -> int:
    from app.modules.billing.models import Invoice, PaymentAllocation

    now = utc_now()
    allocated = (
        select(func.coalesce(func.sum(PaymentAllocation.amount), 0))
        .where(PaymentAllocation.invoice_id == Invoice.id)
        .correlate(Invoice)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Invoice, StudentProfile.user_id)
        .join(StudentProfile, StudentProfile.id == Invoice.student_id)
        .where(
            Invoice.due_at < now,
            Invoice.total > allocated,
            ~exists().where(
                OutboxEvent.event_type == "PAYMENT_DUE",
                OutboxEvent.aggregate_id == Invoice.id,
            ),
        )
        .order_by(Invoice.due_at, Invoice.id)
        .limit(100)
        .with_for_update(skip_locked=True)
    ).all()
    for invoice, recipient_user_id in rows:
        enqueue_notification(
            db,
            event_type="PAYMENT_DUE",
            aggregate_id=invoice.id,
            recipient_user_id=recipient_user_id,
            title="Есть просроченное начисление",
            body="Откройте раздел финансов, чтобы проверить непогашенный остаток.",
            target_type="INVOICE",
            target_id=invoice.id,
            deduplication_key=f"payment-due:{invoice.id}",
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return 0
    return len(rows)


def process_outbox(db: Session, *, batch_size: int = 100) -> int:
    now = utc_now()
    events = db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.status == "PENDING", OutboxEvent.next_attempt_at <= now)
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    sent = 0
    for event in events:
        try:
            with db.begin_nested():
                recipient = UUID(str(event.payload["recipient_user_id"]))
                target_value = event.payload.get("target_id")
                db.add(
                    Notification(
                        recipient_user_id=recipient,
                        type=event.event_type,
                        title=str(event.payload["title"]),
                        body=str(event.payload["body"]),
                        target_type=(
                            str(event.payload["target_type"])
                            if event.payload.get("target_type")
                            else None
                        ),
                        target_id=UUID(str(target_value)) if target_value else None,
                        read_at=None,
                        deduplication_key=f"outbox:{event.id}",
                        created_at=now,
                    )
                )
                db.flush()
            event.status = "SENT"
            event.sent_at = now
            event.attempt_count += 1
            event.last_error = None
            sent += 1
        except (KeyError, TypeError, ValueError, IntegrityError) as exc:
            event.attempt_count += 1
            event.next_attempt_at = now + timedelta(
                minutes=min(60, 2 ** min(event.attempt_count, 5))
            )
            event.last_error = str(exc)[:500]
    db.commit()
    return sent


def notification_response(item: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=item.id,
        type=item.type,
        title=item.title,
        body=item.body,
        target_type=item.target_type,
        target_id=item.target_id,
        read_at=item.read_at,
        created_at=item.created_at,
    )


def list_notifications(
    db: Session,
    user: User,
    *,
    notification_type: str | None,
    is_read: bool | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> NotificationPage:
    filters = [Notification.recipient_user_id == user.id]
    if notification_type:
        filters.append(Notification.type == notification_type)
    if is_read is not None:
        filters.append(
            Notification.read_at.is_not(None) if is_read else Notification.read_at.is_(None)
        )
    if date_from is not None:
        filters.append(Notification.created_at >= date_from)
    if date_to is not None:
        filters.append(Notification.created_at < date_to)
    total = db.scalar(select(func.count(Notification.id)).where(*filters)) or 0
    items = db.scalars(
        select(Notification)
        .where(*filters)
        .order_by(Notification.created_at.desc(), Notification.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return NotificationPage(
        items=[notification_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


def mark_notification_read(db: Session, notification_id: UUID, user: User) -> NotificationResponse:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == user.id,
        )
    )
    if item is None:
        raise NotificationNotFoundError("Уведомление не найдено")
    if item.read_at is None:
        item.read_at = utc_now()
        db.commit()
        db.refresh(item)
    return notification_response(item)


def mark_all_read(db: Session, user: User) -> int:
    items = db.scalars(
        select(Notification).where(
            Notification.recipient_user_id == user.id,
            Notification.read_at.is_(None),
        )
    ).all()
    now = utc_now()
    for item in items:
        item.read_at = now
    db.commit()
    return len(items)
