from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit
from app.modules.scheduling.models import (
    AvailabilityException,
    AvailabilityExceptionKind,
    AvailabilityRule,
    StudentAvailability,
    StudentAvailabilityState,
)
from app.modules.scheduling.schemas import (
    AvailabilityExceptionRequest,
    AvailabilityExceptionResponse,
    AvailabilityRuleRequest,
    AvailabilityRuleResponse,
    StudentAvailabilityRequest,
    StudentAvailabilityResponse,
)


class AvailabilityError(Exception):
    pass


class AvailabilityNotFoundError(AvailabilityError):
    pass


class AvailabilityConflictError(AvailabilityError):
    pass


def utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def stored_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def week_matches(day: date, anchor: date, parity: str) -> bool:
    if parity == "ALL":
        return True
    week_number = (day - anchor).days // 7
    return (week_number % 2 == 0 and parity == "A") or (week_number % 2 == 1 and parity == "B")


def rule_response(rule: AvailabilityRule) -> AvailabilityRuleResponse:
    return AvailabilityRuleResponse(
        id=rule.id,
        timezone=rule.timezone,
        weekday=rule.weekday,
        local_start_time=rule.local_start_time,
        local_end_time=rule.local_end_time,
        week_parity=rule.week_parity,
        cycle_anchor_date=rule.cycle_anchor_date,
        effective_from=rule.effective_from,
        effective_until=rule.effective_until,
        is_available=rule.is_available,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def exception_response(item: AvailabilityException) -> AvailabilityExceptionResponse:
    return AvailabilityExceptionResponse(
        id=item.id,
        starts_at=stored_utc(item.starts_at),
        ends_at=stored_utc(item.ends_at),
        kind=item.kind,
        private_reason=item.private_reason,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def list_rules(db: Session, teacher_id: UUID) -> list[AvailabilityRuleResponse]:
    rules = db.scalars(
        select(AvailabilityRule)
        .where(AvailabilityRule.teacher_id == teacher_id)
        .order_by(AvailabilityRule.weekday, AvailabilityRule.local_start_time)
    ).all()
    return [rule_response(rule) for rule in rules]


def create_rule(
    db: Session, payload: AvailabilityRuleRequest, teacher: User
) -> AvailabilityRuleResponse:
    rule = AvailabilityRule(teacher_id=teacher.id, **payload.model_dump())
    db.add(rule)
    db.flush()
    add_audit(db, teacher.id, "AVAILABILITY_RULE_CREATED", "availability_rule", rule.id)
    db.commit()
    db.refresh(rule)
    return rule_response(rule)


def update_rule(
    db: Session, rule_id: UUID, payload: AvailabilityRuleRequest, teacher: User
) -> AvailabilityRuleResponse:
    rule = db.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id, AvailabilityRule.teacher_id == teacher.id
        )
    )
    if rule is None:
        raise AvailabilityNotFoundError("Правило доступности не найдено")
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    add_audit(db, teacher.id, "AVAILABILITY_RULE_UPDATED", "availability_rule", rule.id)
    db.commit()
    db.refresh(rule)
    return rule_response(rule)


def delete_rule(db: Session, rule_id: UUID, teacher: User) -> None:
    rule = db.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.id == rule_id, AvailabilityRule.teacher_id == teacher.id
        )
    )
    if rule is None:
        raise AvailabilityNotFoundError("Правило доступности не найдено")
    add_audit(db, teacher.id, "AVAILABILITY_RULE_DELETED", "availability_rule", rule.id)
    db.delete(rule)
    db.commit()


def list_exceptions(db: Session, teacher_id: UUID) -> list[AvailabilityExceptionResponse]:
    items = db.scalars(
        select(AvailabilityException)
        .where(AvailabilityException.teacher_id == teacher_id)
        .order_by(AvailabilityException.starts_at)
    ).all()
    return [exception_response(item) for item in items]


def ensure_exception_does_not_overlap(
    db: Session,
    teacher_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: UUID | None = None,
) -> None:
    query = select(AvailabilityException.id).where(
        AvailabilityException.teacher_id == teacher_id,
        AvailabilityException.starts_at < ends_at,
        AvailabilityException.ends_at > starts_at,
    )
    if exclude_id is not None:
        query = query.where(AvailabilityException.id != exclude_id)
    if db.scalar(query.limit(1)) is not None:
        raise AvailabilityConflictError("Исключение пересекается с существующим")


def create_exception(
    db: Session, payload: AvailabilityExceptionRequest, teacher: User
) -> AvailabilityExceptionResponse:
    starts_at, ends_at = utc(payload.starts_at), utc(payload.ends_at)
    ensure_exception_does_not_overlap(db, teacher.id, starts_at, ends_at)
    item = AvailabilityException(
        teacher_id=teacher.id,
        starts_at=starts_at,
        ends_at=ends_at,
        kind=payload.kind,
        private_reason=payload.private_reason.strip() if payload.private_reason else None,
    )
    db.add(item)
    try:
        db.flush()
        add_audit(
            db, teacher.id, "AVAILABILITY_EXCEPTION_CREATED", "availability_exception", item.id
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AvailabilityConflictError("Исключение пересекается с существующим") from exc
    db.refresh(item)
    return exception_response(item)


def update_exception(
    db: Session, item_id: UUID, payload: AvailabilityExceptionRequest, teacher: User
) -> AvailabilityExceptionResponse:
    item = db.scalar(
        select(AvailabilityException).where(
            AvailabilityException.id == item_id,
            AvailabilityException.teacher_id == teacher.id,
        )
    )
    if item is None:
        raise AvailabilityNotFoundError("Исключение не найдено")
    starts_at, ends_at = utc(payload.starts_at), utc(payload.ends_at)
    ensure_exception_does_not_overlap(db, teacher.id, starts_at, ends_at, item.id)
    item.starts_at = starts_at
    item.ends_at = ends_at
    item.kind = payload.kind
    item.private_reason = payload.private_reason.strip() if payload.private_reason else None
    try:
        add_audit(
            db, teacher.id, "AVAILABILITY_EXCEPTION_UPDATED", "availability_exception", item.id
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AvailabilityConflictError("Исключение пересекается с существующим") from exc
    db.refresh(item)
    return exception_response(item)


def delete_exception(db: Session, item_id: UUID, teacher: User) -> None:
    item = db.scalar(
        select(AvailabilityException).where(
            AvailabilityException.id == item_id,
            AvailabilityException.teacher_id == teacher.id,
        )
    )
    if item is None:
        raise AvailabilityNotFoundError("Исключение не найдено")
    add_audit(db, teacher.id, "AVAILABILITY_EXCEPTION_DELETED", "availability_exception", item.id)
    db.delete(item)
    db.commit()


def ensure_teacher_available(
    db: Session, teacher_id: UUID, starts_at: datetime, ends_at: datetime
) -> None:
    starts_at, ends_at = utc(starts_at), utc(ends_at)
    exceptions = db.scalars(
        select(AvailabilityException).where(
            AvailabilityException.teacher_id == teacher_id,
            AvailabilityException.starts_at < ends_at,
            AvailabilityException.ends_at > starts_at,
        )
    ).all()
    if any(item.kind == AvailabilityExceptionKind.BLOCKED for item in exceptions):
        raise AvailabilityConflictError("Преподаватель недоступен в выбранное время")
    if any(
        item.kind == AvailabilityExceptionKind.AVAILABLE_OVERRIDE
        and stored_utc(item.starts_at) <= starts_at
        and stored_utc(item.ends_at) >= ends_at
        for item in exceptions
    ):
        return

    rules = db.scalars(
        select(AvailabilityRule).where(AvailabilityRule.teacher_id == teacher_id)
    ).all()
    if not rules:
        return

    matching: list[AvailabilityRule] = []
    for rule in rules:
        zone = ZoneInfo(rule.timezone)
        local_start = starts_at.astimezone(zone)
        local_end = ends_at.astimezone(zone)
        day = local_start.date()
        if local_end.date() != day:
            continue
        if not (
            rule.effective_from <= day
            and (rule.effective_until is None or day <= rule.effective_until)
        ):
            continue
        if rule.weekday != day.weekday() or not week_matches(
            day, rule.cycle_anchor_date, rule.week_parity
        ):
            continue
        if rule.local_start_time <= local_start.time().replace(
            tzinfo=None
        ) and rule.local_end_time >= local_end.time().replace(tzinfo=None):
            matching.append(rule)
    if any(not rule.is_available for rule in matching) or not any(
        rule.is_available for rule in matching
    ):
        raise AvailabilityConflictError("Урок не помещается в доступное время преподавателя")


def student_response(db: Session, item: StudentAvailability) -> StudentAvailabilityResponse:
    from app.modules.lessons.models import Lesson, LessonStatus

    conflict = False
    if item.state == StudentAvailabilityState.BUSY:
        conflict = (
            db.scalar(
                select(Lesson.id)
                .where(
                    Lesson.student_id == item.student_id,
                    Lesson.status == LessonStatus.SCHEDULED,
                    Lesson.starts_at < item.ends_at,
                    Lesson.ends_at > item.starts_at,
                )
                .limit(1)
            )
            is not None
        )
    return StudentAvailabilityResponse(
        id=item.id,
        starts_at=stored_utc(item.starts_at),
        ends_at=stored_utc(item.ends_at),
        state=item.state,
        conflicts_with_lesson=conflict,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def list_student_availability(db: Session, profile_id: UUID) -> list[StudentAvailabilityResponse]:
    items = db.scalars(
        select(StudentAvailability)
        .where(StudentAvailability.student_id == profile_id)
        .order_by(StudentAvailability.starts_at)
    ).all()
    return [student_response(db, item) for item in items]


def ensure_student_mark_does_not_overlap(
    db: Session,
    profile_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: UUID | None = None,
) -> None:
    query = select(StudentAvailability.id).where(
        StudentAvailability.student_id == profile_id,
        StudentAvailability.starts_at < ends_at,
        StudentAvailability.ends_at > starts_at,
    )
    if exclude_id is not None:
        query = query.where(StudentAvailability.id != exclude_id)
    if db.scalar(query.limit(1)) is not None:
        raise AvailabilityConflictError("Отметка пересекается с существующей")


def create_student_mark(
    db: Session, profile: StudentProfile, payload: StudentAvailabilityRequest, actor: User
) -> StudentAvailabilityResponse:
    starts_at, ends_at = utc(payload.starts_at), utc(payload.ends_at)
    ensure_student_mark_does_not_overlap(db, profile.id, starts_at, ends_at)
    item = StudentAvailability(
        student_id=profile.id, starts_at=starts_at, ends_at=ends_at, state=payload.state
    )
    db.add(item)
    try:
        db.flush()
        add_audit(db, actor.id, "STUDENT_AVAILABILITY_CREATED", "student_availability", item.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AvailabilityConflictError("Отметка пересекается с существующей") from exc
    db.refresh(item)
    return student_response(db, item)


def update_student_mark(
    db: Session,
    profile: StudentProfile,
    item_id: UUID,
    payload: StudentAvailabilityRequest,
    actor: User,
) -> StudentAvailabilityResponse:
    item = db.scalar(
        select(StudentAvailability).where(
            StudentAvailability.id == item_id,
            StudentAvailability.student_id == profile.id,
        )
    )
    if item is None:
        raise AvailabilityNotFoundError("Отметка доступности не найдена")
    starts_at, ends_at = utc(payload.starts_at), utc(payload.ends_at)
    ensure_student_mark_does_not_overlap(db, profile.id, starts_at, ends_at, item.id)
    item.starts_at = starts_at
    item.ends_at = ends_at
    item.state = payload.state
    try:
        add_audit(db, actor.id, "STUDENT_AVAILABILITY_UPDATED", "student_availability", item.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AvailabilityConflictError("Отметка пересекается с существующей") from exc
    db.refresh(item)
    return student_response(db, item)


def delete_student_mark(db: Session, profile: StudentProfile, item_id: UUID, actor: User) -> None:
    item = db.scalar(
        select(StudentAvailability).where(
            StudentAvailability.id == item_id,
            StudentAvailability.student_id == profile.id,
        )
    )
    if item is None:
        raise AvailabilityNotFoundError("Отметка доступности не найдена")
    add_audit(db, actor.id, "STUDENT_AVAILABILITY_DELETED", "student_availability", item.id)
    db.delete(item)
    db.commit()
