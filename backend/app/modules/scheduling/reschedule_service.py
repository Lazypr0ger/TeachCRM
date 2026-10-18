from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User
from app.modules.auth.service import add_audit, utc_now
from app.modules.lessons.models import Lesson, LessonStatus
from app.modules.lessons.service import (
    LessonConflictError,
    ensure_no_overlap,
    student_profile_for_user,
)
from app.modules.scheduling.models import (
    RecurrenceExceptionAction,
    RescheduleRequest,
    RescheduleStatus,
)
from app.modules.scheduling.recurrence_service import mark_occurrence_exception
from app.modules.scheduling.reschedule_schemas import (
    RescheduleCounterRequest,
    RescheduleCreateRequest,
    RescheduleDecisionRequest,
    RescheduleResponse,
)
from app.modules.scheduling.service import (
    AvailabilityConflictError,
    ensure_teacher_available,
    stored_utc,
    utc,
)

ACTIVE_STATUSES = (RescheduleStatus.PENDING, RescheduleStatus.COUNTER_OFFER)


class RescheduleError(Exception):
    pass


class RescheduleNotFoundError(RescheduleError):
    pass


class RescheduleConflictError(RescheduleError):
    pass


def student_name(profile: StudentProfile) -> str:
    return " ".join(
        part for part in (profile.last_name, profile.first_name, profile.patronymic) if part
    )


def to_response(
    item: RescheduleRequest, lesson: Lesson, profile: StudentProfile
) -> RescheduleResponse:
    return RescheduleResponse(
        id=item.id,
        lesson_id=item.lesson_id,
        student_id=item.student_id,
        student_name=student_name(profile),
        lesson_title=lesson.title,
        original_starts_at=stored_utc(item.original_starts_at),
        original_ends_at=stored_utc(item.original_ends_at),
        proposed_starts_at=stored_utc(item.proposed_starts_at),
        proposed_ends_at=stored_utc(item.proposed_ends_at),
        reason=item.reason,
        status=item.status,
        counter_starts_at=stored_utc(item.counter_starts_at) if item.counter_starts_at else None,
        counter_ends_at=stored_utc(item.counter_ends_at) if item.counter_ends_at else None,
        response_note=item.response_note,
        responded_at=item.responded_at,
        resolved_at=item.resolved_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def get_request_row(
    db: Session,
    request_id: UUID,
    *,
    student_id: UUID | None = None,
    for_update: bool = False,
) -> tuple[RescheduleRequest, Lesson, StudentProfile]:
    query = (
        select(RescheduleRequest, Lesson, StudentProfile)
        .join(Lesson, Lesson.id == RescheduleRequest.lesson_id)
        .join(StudentProfile, StudentProfile.id == RescheduleRequest.student_id)
        .where(RescheduleRequest.id == request_id)
    )
    if student_id is not None:
        query = query.where(RescheduleRequest.student_id == student_id)
    if for_update:
        query = query.with_for_update()
    row = db.execute(query).one_or_none()
    if row is None:
        raise RescheduleNotFoundError("Запрос переноса не найден")
    return row


def create_request(
    db: Session,
    lesson_id: UUID,
    payload: RescheduleCreateRequest,
    student: User,
) -> RescheduleResponse:
    profile = student_profile_for_user(db, student.id)
    row = db.execute(
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(Lesson.id == lesson_id, Lesson.student_id == profile.id)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise RescheduleNotFoundError("Урок не найден")
    lesson, lesson_profile = row
    if lesson.status != LessonStatus.SCHEDULED:
        raise RescheduleConflictError("Перенос можно запросить только для запланированного урока")
    if stored_utc(lesson.ends_at) <= utc_now():
        raise RescheduleConflictError("Нельзя перенести уже прошедший урок")
    if utc(payload.proposed_starts_at) <= utc_now():
        raise RescheduleConflictError("Новое время должно быть в будущем")
    if (
        db.scalar(
            select(RescheduleRequest.id).where(
                RescheduleRequest.lesson_id == lesson.id,
                RescheduleRequest.status.in_(ACTIVE_STATUSES),
            )
        )
        is not None
    ):
        raise RescheduleConflictError("Для урока уже есть активный запрос переноса")
    item = RescheduleRequest(
        lesson_id=lesson.id,
        student_id=profile.id,
        original_starts_at=stored_utc(lesson.starts_at),
        original_ends_at=stored_utc(lesson.ends_at),
        proposed_starts_at=utc(payload.proposed_starts_at),
        proposed_ends_at=utc(payload.proposed_ends_at),
        reason=payload.reason.strip() if payload.reason else None,
        status=RescheduleStatus.PENDING,
    )
    db.add(item)
    try:
        db.flush()
        add_audit(db, student.id, "RESCHEDULE_REQUESTED", "reschedule_request", item.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RescheduleConflictError("Для урока уже есть активный запрос переноса") from exc
    db.refresh(item)
    return to_response(item, lesson, lesson_profile)


def list_student_requests(db: Session, student: User) -> list[RescheduleResponse]:
    profile = student_profile_for_user(db, student.id)
    rows = db.execute(
        select(RescheduleRequest, Lesson, StudentProfile)
        .join(Lesson, Lesson.id == RescheduleRequest.lesson_id)
        .join(StudentProfile, StudentProfile.id == RescheduleRequest.student_id)
        .where(RescheduleRequest.student_id == profile.id)
        .order_by(RescheduleRequest.created_at.desc())
    ).all()
    return [to_response(item, lesson, row_profile) for item, lesson, row_profile in rows]


def list_teacher_requests(db: Session, request_status: str | None) -> list[RescheduleResponse]:
    query = (
        select(RescheduleRequest, Lesson, StudentProfile)
        .join(Lesson, Lesson.id == RescheduleRequest.lesson_id)
        .join(StudentProfile, StudentProfile.id == RescheduleRequest.student_id)
    )
    if request_status is not None:
        query = query.where(RescheduleRequest.status == request_status)
    rows = db.execute(query.order_by(RescheduleRequest.created_at.desc())).all()
    return [to_response(item, lesson, profile) for item, lesson, profile in rows]


def ensure_request_is_current(item: RescheduleRequest, lesson: Lesson) -> None:
    if lesson.status != LessonStatus.SCHEDULED:
        raise RescheduleConflictError("Урок больше не запланирован")
    if stored_utc(lesson.starts_at) != stored_utc(item.original_starts_at) or stored_utc(
        lesson.ends_at
    ) != stored_utc(item.original_ends_at):
        raise RescheduleConflictError("Урок уже был изменён после создания запроса")


def validate_destination(
    db: Session, lesson: Lesson, starts_at: datetime, ends_at: datetime
) -> None:
    if starts_at <= utc_now():
        raise RescheduleConflictError("Новое время должно быть в будущем")
    try:
        ensure_teacher_available(db, lesson.teacher_id, starts_at, ends_at)
    except AvailabilityConflictError as exc:
        raise RescheduleConflictError(str(exc)) from exc
    try:
        ensure_no_overlap(
            db,
            teacher_id=lesson.teacher_id,
            student_id=lesson.student_id,
            starts_at=starts_at,
            ends_at=ends_at,
            exclude_id=lesson.id,
        )
    except LessonConflictError as exc:
        raise RescheduleConflictError(str(exc)) from exc


def apply_move(
    db: Session,
    item: RescheduleRequest,
    lesson: Lesson,
    starts_at: datetime,
    ends_at: datetime,
    actor: User,
) -> None:
    ensure_request_is_current(item, lesson)
    validate_destination(db, lesson, starts_at, ends_at)
    lesson.starts_at = starts_at
    lesson.ends_at = ends_at
    lesson.version += 1
    mark_occurrence_exception(db, lesson, RecurrenceExceptionAction.MODIFIED)
    item.status = RescheduleStatus.ACCEPTED
    item.responded_at = item.responded_at or utc_now()
    item.resolved_at = utc_now()
    add_audit(db, actor.id, "RESCHEDULE_ACCEPTED", "reschedule_request", item.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RescheduleConflictError("Новое время пересекается с другим уроком") from exc


def teacher_accept(db: Session, request_id: UUID, teacher: User) -> RescheduleResponse:
    item, lesson, profile = get_request_row(db, request_id, for_update=True)
    if item.status != RescheduleStatus.PENDING:
        raise RescheduleConflictError("Принять можно только ожидающий запрос")
    apply_move(
        db,
        item,
        lesson,
        stored_utc(item.proposed_starts_at),
        stored_utc(item.proposed_ends_at),
        teacher,
    )
    db.refresh(item)
    return to_response(item, lesson, profile)


def teacher_counter(
    db: Session,
    request_id: UUID,
    payload: RescheduleCounterRequest,
    teacher: User,
) -> RescheduleResponse:
    item, lesson, profile = get_request_row(db, request_id, for_update=True)
    if item.status != RescheduleStatus.PENDING:
        raise RescheduleConflictError("Встречный вариант доступен только для ожидающего запроса")
    ensure_request_is_current(item, lesson)
    starts_at, ends_at = utc(payload.counter_starts_at), utc(payload.counter_ends_at)
    validate_destination(db, lesson, starts_at, ends_at)
    item.counter_starts_at = starts_at
    item.counter_ends_at = ends_at
    item.response_note = payload.response_note.strip() if payload.response_note else None
    item.status = RescheduleStatus.COUNTER_OFFER
    item.responded_at = utc_now()
    add_audit(db, teacher.id, "RESCHEDULE_COUNTERED", "reschedule_request", item.id)
    db.commit()
    db.refresh(item)
    return to_response(item, lesson, profile)


def teacher_reject(
    db: Session,
    request_id: UUID,
    payload: RescheduleDecisionRequest,
    teacher: User,
) -> RescheduleResponse:
    item, lesson, profile = get_request_row(db, request_id, for_update=True)
    if item.status not in ACTIVE_STATUSES:
        raise RescheduleConflictError("Запрос уже завершён")
    item.status = RescheduleStatus.REJECTED
    item.response_note = payload.response_note.strip() if payload.response_note else None
    item.responded_at = utc_now()
    item.resolved_at = item.responded_at
    add_audit(db, teacher.id, "RESCHEDULE_REJECTED", "reschedule_request", item.id)
    db.commit()
    db.refresh(item)
    return to_response(item, lesson, profile)


def student_accept_counter(db: Session, request_id: UUID, student: User) -> RescheduleResponse:
    profile = student_profile_for_user(db, student.id)
    item, lesson, row_profile = get_request_row(
        db, request_id, student_id=profile.id, for_update=True
    )
    if (
        item.status != RescheduleStatus.COUNTER_OFFER
        or item.counter_starts_at is None
        or item.counter_ends_at is None
    ):
        raise RescheduleConflictError("Встречное предложение недоступно")
    apply_move(
        db,
        item,
        lesson,
        stored_utc(item.counter_starts_at),
        stored_utc(item.counter_ends_at),
        student,
    )
    db.refresh(item)
    return to_response(item, lesson, row_profile)


def student_cancel(db: Session, request_id: UUID, student: User) -> RescheduleResponse:
    profile = student_profile_for_user(db, student.id)
    item, lesson, row_profile = get_request_row(
        db, request_id, student_id=profile.id, for_update=True
    )
    if item.status not in ACTIVE_STATUSES:
        raise RescheduleConflictError("Запрос уже завершён")
    item.status = RescheduleStatus.CANCELLED
    item.resolved_at = utc_now()
    add_audit(db, student.id, "RESCHEDULE_CANCELLED", "reschedule_request", item.id)
    db.commit()
    db.refresh(item)
    return to_response(item, lesson, row_profile)


def cancel_active_for_lesson(db: Session, lesson_id: UUID) -> None:
    items = db.scalars(
        select(RescheduleRequest).where(
            RescheduleRequest.lesson_id == lesson_id,
            RescheduleRequest.status.in_(ACTIVE_STATUSES),
        )
    ).all()
    now = utc_now()
    for item in items:
        item.status = RescheduleStatus.CANCELLED
        item.resolved_at = now
