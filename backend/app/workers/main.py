import logging
import signal
import time
from types import FrameType

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import create_db_engine, create_session_factory, database_is_ready
from app.core.observability import configure_logging
from app.modules.files.service import cleanup_expired_uploads
from app.modules.files.storage import get_storage
from app.modules.notifications.service import enqueue_payment_due_notifications, process_outbox
from app.modules.scheduling.models import LessonRecurrenceRule
from app.modules.scheduling.recurrence_service import RecurrenceConflictError, materialize_rule

configure_logging()
logger = logging.getLogger(__name__)
running = True
RECURRENCE_INTERVAL_SECONDS = 300
FILE_CLEANUP_INTERVAL_SECONDS = 900
OUTBOX_INTERVAL_SECONDS = 10
PAYMENT_DUE_INTERVAL_SECONDS = 300


def stop(_signum: int, _frame: FrameType | None) -> None:
    global running
    running = False


def materialize_recurrences(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        rule_ids = db.scalars(
            select(LessonRecurrenceRule.id).where(LessonRecurrenceRule.active.is_(True))
        ).all()
    for rule_id in rule_ids:
        with factory() as db:
            rule = db.get(LessonRecurrenceRule, rule_id)
            if rule is None or not rule.active:
                continue
            try:
                created = materialize_rule(db, rule)
                db.commit()
                if created:
                    logger.info("recurrence_materialized rule_id=%s count=%s", rule_id, created)
            except (RecurrenceConflictError, IntegrityError):
                db.rollback()
                logger.exception("recurrence_materialization_conflict rule_id=%s", rule_id)


def clean_expired_uploads(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        try:
            deleted = cleanup_expired_uploads(db, get_storage())
            if deleted:
                logger.info("expired_uploads_deleted count=%s", deleted)
        except Exception:
            db.rollback()
            logger.exception("expired_upload_cleanup_failed")


def deliver_notifications(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        try:
            delivered = process_outbox(db)
            if delivered:
                logger.info("notifications_delivered count=%s", delivered)
        except Exception:
            db.rollback()
            logger.exception("notification_delivery_failed")


def enqueue_payment_reminders(factory: sessionmaker[Session]) -> None:
    with factory() as db:
        try:
            created = enqueue_payment_due_notifications(db)
            if created:
                logger.info("payment_due_notifications_enqueued count=%s", created)
        except Exception:
            db.rollback()
            logger.exception("payment_due_notification_failed")


def run() -> None:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("worker_started")
    next_recurrence_run = 0.0
    next_file_cleanup_run = 0.0
    next_outbox_run = 0.0
    next_payment_due_run = 0.0
    while running:
        database_is_ready(engine)
        if time.monotonic() >= next_recurrence_run:
            materialize_recurrences(session_factory)
            next_recurrence_run = time.monotonic() + RECURRENCE_INTERVAL_SECONDS
        if time.monotonic() >= next_file_cleanup_run:
            clean_expired_uploads(session_factory)
            next_file_cleanup_run = time.monotonic() + FILE_CLEANUP_INTERVAL_SECONDS
        if time.monotonic() >= next_outbox_run:
            deliver_notifications(session_factory)
            next_outbox_run = time.monotonic() + OUTBOX_INTERVAL_SECONDS
        if time.monotonic() >= next_payment_due_run:
            enqueue_payment_reminders(session_factory)
            next_payment_due_run = time.monotonic() + PAYMENT_DUE_INTERVAL_SECONDS
        time.sleep(5)
    engine.dispose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    run()
