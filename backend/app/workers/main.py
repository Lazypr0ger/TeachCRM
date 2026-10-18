import logging
import signal
import time
from types import FrameType

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.db import create_db_engine, create_session_factory, database_is_ready
from app.modules.scheduling.models import LessonRecurrenceRule
from app.modules.scheduling.recurrence_service import RecurrenceConflictError, materialize_rule

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
running = True
RECURRENCE_INTERVAL_SECONDS = 300


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


def run() -> None:
    settings = get_settings()
    engine = create_db_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    logger.info("worker_started")
    next_recurrence_run = 0.0
    while running:
        database_is_ready(engine)
        if time.monotonic() >= next_recurrence_run:
            materialize_recurrences(session_factory)
            next_recurrence_run = time.monotonic() + RECURRENCE_INTERVAL_SECONDS
        time.sleep(5)
    engine.dispose()
    logger.info("worker_stopped")


if __name__ == "__main__":
    run()
