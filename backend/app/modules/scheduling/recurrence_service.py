from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit, utc_now
from app.modules.lessons.models import Lesson, LessonStatus
from app.modules.lessons.service import (
    LessonConflictError,
    active_student,
    ensure_no_overlap,
)
from app.modules.scheduling.models import (
    LessonRecurrenceRule,
    RecurrenceException,
    RecurrenceExceptionAction,
)
from app.modules.scheduling.recurrence_schemas import (
    RecurrenceRuleCreateRequest,
    RecurrenceRuleResponse,
    RecurrenceRuleUpdateRequest,
)
from app.modules.scheduling.service import AvailabilityConflictError, ensure_teacher_available

HORIZON_WEEKS = 12


class RecurrenceError(Exception):
    pass


class RecurrenceNotFoundError(RecurrenceError):
    pass


class RecurrenceConflictError(RecurrenceError):
    pass


class RecurrenceVersionError(RecurrenceError):
    pass


def profile_name(profile: StudentProfile) -> str:
    return " ".join(
        part for part in (profile.last_name, profile.first_name, profile.patronymic) if part
    )


def response(
    rule: LessonRecurrenceRule,
    profile: StudentProfile,
    materialized_count: int = 0,
) -> RecurrenceRuleResponse:
    return RecurrenceRuleResponse(
        id=rule.id,
        teacher_id=rule.teacher_id,
        student_id=rule.student_id,
        student_name=profile_name(profile),
        title=rule.title,
        description=rule.description,
        join_url=rule.join_url,
        local_time=rule.local_time,
        duration_minutes=rule.duration_minutes,
        timezone=rule.timezone,
        by_weekday=rule.by_weekday,
        interval_weeks=rule.interval_weeks,
        starts_on=rule.starts_on,
        ends_on=rule.ends_on,
        count_limit=rule.count_limit,
        active=rule.active,
        version=rule.version,
        materialized_count=materialized_count,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def occurrence_dates(
    rule: LessonRecurrenceRule, today: date | None = None
) -> list[tuple[date, str]]:
    zone_today = today or datetime.now(ZoneInfo(rule.timezone)).date()
    horizon = max(zone_today, rule.starts_on) + timedelta(weeks=HORIZON_WEEKS)
    result: list[tuple[date, str]] = []
    occurrence = rule.starts_on
    ordinal = 0
    while occurrence < horizon:
        ordinal += 1
        if rule.count_limit is not None and ordinal > rule.count_limit:
            break
        if rule.ends_on is not None and occurrence > rule.ends_on:
            break
        if occurrence >= zone_today:
            result.append((occurrence, occurrence.isoformat()))
        occurrence += timedelta(weeks=rule.interval_weeks)
    return result


def materialize_rule(db: Session, rule: LessonRecurrenceRule, *, today: date | None = None) -> int:
    if not rule.active:
        return 0
    created = 0
    zone = ZoneInfo(rule.timezone)
    for occurrence, key in occurrence_dates(rule, today):
        if (
            db.scalar(
                select(RecurrenceException.id).where(
                    RecurrenceException.rule_id == rule.id,
                    RecurrenceException.occurrence_key == key,
                )
            )
            is not None
        ):
            continue
        if (
            db.scalar(
                select(Lesson.id).where(
                    Lesson.recurrence_rule_id == rule.id,
                    Lesson.recurrence_instance_key == key,
                )
            )
            is not None
        ):
            continue
        starts_at = datetime.combine(occurrence, rule.local_time, zone).astimezone(UTC)
        ends_at = starts_at + timedelta(minutes=rule.duration_minutes)
        if ends_at <= utc_now():
            continue
        try:
            ensure_teacher_available(db, rule.teacher_id, starts_at, ends_at)
        except AvailabilityConflictError as exc:
            raise RecurrenceConflictError(f"{occurrence}: {exc}") from exc
        try:
            ensure_no_overlap(
                db,
                teacher_id=rule.teacher_id,
                student_id=rule.student_id,
                starts_at=starts_at,
                ends_at=ends_at,
            )
        except LessonConflictError as exc:
            raise RecurrenceConflictError(f"{occurrence}: {exc}") from exc
        db.add(
            Lesson(
                teacher_id=rule.teacher_id,
                student_id=rule.student_id,
                title=rule.title,
                description=rule.description,
                starts_at=starts_at,
                ends_at=ends_at,
                join_url=rule.join_url,
                status=LessonStatus.SCHEDULED,
                recurrence_rule_id=rule.id,
                recurrence_instance_key=key,
            )
        )
        db.flush()
        created += 1
    return created


def create_recurrence_rule(
    db: Session, payload: RecurrenceRuleCreateRequest, teacher: User
) -> RecurrenceRuleResponse:
    profile, _student_user = active_student(db, payload.student_id)
    rule = LessonRecurrenceRule(
        teacher_id=teacher.id,
        student_id=profile.id,
        **payload.model_dump(exclude={"student_id"}),
    )
    if rule.description:
        rule.description = rule.description.strip() or None
    db.add(rule)
    try:
        db.flush()
        count = materialize_rule(db, rule)
        add_audit(db, teacher.id, "RECURRENCE_RULE_CREATED", "recurrence_rule", rule.id)
        db.commit()
    except (IntegrityError, RecurrenceConflictError) as exc:
        db.rollback()
        if isinstance(exc, RecurrenceConflictError):
            raise
        raise RecurrenceConflictError("Не удалось создать серию из-за конфликта") from exc
    db.refresh(rule)
    return response(rule, profile, count)


def list_recurrence_rules(db: Session, teacher_id: UUID) -> list[RecurrenceRuleResponse]:
    rows = db.execute(
        select(LessonRecurrenceRule, StudentProfile)
        .join(StudentProfile, StudentProfile.id == LessonRecurrenceRule.student_id)
        .where(LessonRecurrenceRule.teacher_id == teacher_id)
        .order_by(LessonRecurrenceRule.created_at.desc())
    ).all()
    return [response(rule, profile) for rule, profile in rows]


def get_rule(
    db: Session, rule_id: UUID, teacher_id: UUID, *, for_update: bool = False
) -> tuple[LessonRecurrenceRule, StudentProfile]:
    query = (
        select(LessonRecurrenceRule, StudentProfile)
        .join(StudentProfile, StudentProfile.id == LessonRecurrenceRule.student_id)
        .where(
            LessonRecurrenceRule.id == rule_id,
            LessonRecurrenceRule.teacher_id == teacher_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    row = db.execute(query).one_or_none()
    if row is None:
        raise RecurrenceNotFoundError("Серия не найдена")
    return row


def update_recurrence_rule(
    db: Session,
    rule_id: UUID,
    payload: RecurrenceRuleUpdateRequest,
    teacher: User,
) -> RecurrenceRuleResponse:
    rule, profile = get_rule(db, rule_id, teacher.id, for_update=True)
    if rule.version != payload.version:
        raise RecurrenceVersionError("Серия уже изменена в другой вкладке")
    changes = payload.model_dump(exclude={"version"}, exclude_unset=True)
    for field, value in changes.items():
        if field in {"description", "join_url"} and value == "":
            value = None
        setattr(rule, field, value)
    rule.version += 1
    exception_keys = set(
        db.scalars(
            select(RecurrenceException.occurrence_key).where(RecurrenceException.rule_id == rule.id)
        ).all()
    )
    future_lessons = db.scalars(
        select(Lesson).where(
            Lesson.recurrence_rule_id == rule.id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at >= utc_now(),
        )
    ).all()
    for lesson in future_lessons:
        if lesson.recurrence_instance_key in exception_keys:
            continue
        if "title" in changes:
            lesson.title = rule.title
        if "description" in changes:
            lesson.description = rule.description
        if "join_url" in changes:
            lesson.join_url = rule.join_url
        lesson.version += 1
    try:
        count = materialize_rule(db, rule) if rule.active else 0
        add_audit(db, teacher.id, "RECURRENCE_RULE_UPDATED", "recurrence_rule", rule.id)
        db.commit()
    except (IntegrityError, RecurrenceConflictError) as exc:
        db.rollback()
        if isinstance(exc, RecurrenceConflictError):
            raise
        raise RecurrenceConflictError("Не удалось обновить серию") from exc
    db.refresh(rule)
    return response(rule, profile, count)


def deactivate_recurrence_rule(db: Session, rule_id: UUID, teacher: User) -> None:
    rule, _profile = get_rule(db, rule_id, teacher.id, for_update=True)
    if not rule.active:
        return
    rule.active = False
    rule.version += 1
    lessons = db.scalars(
        select(Lesson).where(
            Lesson.recurrence_rule_id == rule.id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at >= utc_now(),
        )
    ).all()
    for lesson in lessons:
        lesson.status = LessonStatus.CANCELLED
        lesson.version += 1
        mark_occurrence_exception(db, lesson, RecurrenceExceptionAction.CANCELLED)
    add_audit(db, teacher.id, "RECURRENCE_RULE_DEACTIVATED", "recurrence_rule", rule.id)
    db.commit()


def rematerialize_rule(
    db: Session, rule_id: UUID, teacher: User, *, today: date | None = None
) -> RecurrenceRuleResponse:
    rule, profile = get_rule(db, rule_id, teacher.id, for_update=True)
    try:
        count = materialize_rule(db, rule, today=today)
        db.commit()
    except (IntegrityError, RecurrenceConflictError) as exc:
        db.rollback()
        if isinstance(exc, RecurrenceConflictError):
            raise
        raise RecurrenceConflictError("Не удалось достроить серию") from exc
    db.refresh(rule)
    return response(rule, profile, count)


def mark_occurrence_exception(db: Session, lesson: Lesson, action: str) -> None:
    if lesson.recurrence_rule_id is None or lesson.recurrence_instance_key is None:
        return
    item = db.scalar(
        select(RecurrenceException).where(
            RecurrenceException.rule_id == lesson.recurrence_rule_id,
            RecurrenceException.occurrence_key == lesson.recurrence_instance_key,
        )
    )
    if item is None:
        db.add(
            RecurrenceException(
                rule_id=lesson.recurrence_rule_id,
                occurrence_key=lesson.recurrence_instance_key,
                action=action,
                replacement_lesson_id=lesson.id
                if action == RecurrenceExceptionAction.MODIFIED
                else None,
            )
        )
    else:
        item.action = action
        item.replacement_lesson_id = (
            lesson.id if action == RecurrenceExceptionAction.MODIFIED else None
        )
