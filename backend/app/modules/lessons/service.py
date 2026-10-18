from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User, UserRole, UserStatus
from app.modules.auth.service import add_audit, utc_now
from app.modules.lessons.models import Lesson, LessonStatus
from app.modules.lessons.schemas import LessonCreateRequest, LessonResponse, LessonUpdateRequest


class LessonError(Exception):
    pass


class LessonNotFoundError(LessonError):
    pass


class LessonConflictError(LessonError):
    pass


class LessonStateError(LessonError):
    pass


class LessonVersionError(LessonError):
    pass


def normalize_datetime(value: datetime) -> datetime:
    return value.astimezone(UTC)


def active_student(db: Session, student_id: UUID) -> tuple[StudentProfile, User]:
    row = db.execute(
        select(StudentProfile, User)
        .join(User, User.id == StudentProfile.user_id)
        .where(
            StudentProfile.id == student_id,
            StudentProfile.active.is_(True),
            User.role == UserRole.STUDENT,
            User.status.in_((UserStatus.INVITED, UserStatus.ACTIVE)),
        )
    ).one_or_none()
    if row is None:
        raise LessonNotFoundError("Активный ученик не найден")
    return row


def student_profile_for_user(db: Session, user_id: UUID) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user_id))
    if profile is None:
        raise LessonNotFoundError("Профиль ученика не найден")
    return profile


def lesson_response(lesson: Lesson, profile: StudentProfile) -> LessonResponse:
    name = " ".join(
        part for part in (profile.last_name, profile.first_name, profile.patronymic) if part
    )
    return LessonResponse(
        id=lesson.id,
        teacher_id=lesson.teacher_id,
        student_id=lesson.student_id,
        student_name=name,
        title=lesson.title,
        description=lesson.description,
        starts_at=lesson.starts_at,
        ends_at=lesson.ends_at,
        join_url=lesson.join_url,
        status=lesson.status,
        recurrence_rule_id=lesson.recurrence_rule_id,
        recurrence_instance_key=lesson.recurrence_instance_key,
        completed_at=lesson.completed_at,
        version=lesson.version,
        created_at=lesson.created_at,
        updated_at=lesson.updated_at,
    )


def ensure_no_overlap(
    db: Session,
    *,
    teacher_id: UUID,
    student_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: UUID | None = None,
) -> None:
    query = select(Lesson.id).where(
        Lesson.status == LessonStatus.SCHEDULED,
        Lesson.starts_at < ends_at,
        Lesson.ends_at > starts_at,
        (Lesson.teacher_id == teacher_id) | (Lesson.student_id == student_id),
    )
    if exclude_id is not None:
        query = query.where(Lesson.id != exclude_id)
    if db.scalar(query.limit(1)) is not None:
        raise LessonConflictError("Время пересекается с другим запланированным уроком")


def create_lesson(db: Session, payload: LessonCreateRequest, teacher: User) -> LessonResponse:
    profile, _student_user = active_student(db, payload.student_id)
    starts_at = normalize_datetime(payload.starts_at)
    ends_at = normalize_datetime(payload.ends_at)
    from app.modules.scheduling.service import (
        AvailabilityConflictError,
        ensure_teacher_available,
    )

    try:
        ensure_teacher_available(db, teacher.id, starts_at, ends_at)
    except AvailabilityConflictError as exc:
        raise LessonConflictError(str(exc)) from exc
    ensure_no_overlap(
        db,
        teacher_id=teacher.id,
        student_id=profile.id,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    lesson = Lesson(
        teacher_id=teacher.id,
        student_id=profile.id,
        title=payload.title,
        description=payload.description.strip() if payload.description else None,
        starts_at=starts_at,
        ends_at=ends_at,
        join_url=payload.join_url,
        status=LessonStatus.SCHEDULED,
    )
    db.add(lesson)
    try:
        db.flush()
        add_audit(db, teacher.id, "LESSON_CREATED", "lesson", lesson.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise LessonConflictError("Время пересекается с другим запланированным уроком") from exc
    db.refresh(lesson)
    return lesson_response(lesson, profile)


def get_lesson_row(
    db: Session,
    lesson_id: UUID,
    student_id: UUID | None = None,
    *,
    for_update: bool = False,
) -> tuple[Lesson, StudentProfile]:
    query = (
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(Lesson.id == lesson_id)
    )
    if student_id is not None:
        query = query.where(Lesson.student_id == student_id)
    if for_update:
        query = query.with_for_update()
    row = db.execute(query).one_or_none()
    if row is None:
        raise LessonNotFoundError("Урок не найден")
    return row


def list_lessons(
    db: Session,
    *,
    student_id: UUID | None,
    lesson_status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[LessonResponse], int]:
    filters = []
    if student_id is not None:
        filters.append(Lesson.student_id == student_id)
    if lesson_status is not None:
        filters.append(Lesson.status == lesson_status)
    if date_from is not None:
        filters.append(Lesson.starts_at >= normalize_datetime(date_from))
    if date_to is not None:
        filters.append(Lesson.starts_at < normalize_datetime(date_to))
    base = (
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.execute(
        base.order_by(Lesson.starts_at, Lesson.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return [lesson_response(lesson, profile) for lesson, profile in rows], total


def update_lesson(
    db: Session, lesson_id: UUID, payload: LessonUpdateRequest, teacher: User
) -> LessonResponse:
    lesson, profile = get_lesson_row(db, lesson_id, for_update=True)
    if lesson.status != LessonStatus.SCHEDULED:
        raise LessonStateError("Можно редактировать только запланированный урок")
    if lesson.version != payload.version:
        raise LessonVersionError("Урок уже изменён в другой вкладке")
    changes = payload.model_dump(exclude={"version"}, exclude_unset=True)
    starts_at = normalize_datetime(changes.get("starts_at", lesson.starts_at))
    ends_at = normalize_datetime(changes.get("ends_at", lesson.ends_at))
    if ends_at <= starts_at:
        raise LessonStateError("Окончание урока должно быть позже начала")
    from app.modules.scheduling.service import (
        AvailabilityConflictError,
        ensure_teacher_available,
    )

    try:
        ensure_teacher_available(db, lesson.teacher_id, starts_at, ends_at)
    except AvailabilityConflictError as exc:
        raise LessonConflictError(str(exc)) from exc
    ensure_no_overlap(
        db,
        teacher_id=lesson.teacher_id,
        student_id=lesson.student_id,
        starts_at=starts_at,
        ends_at=ends_at,
        exclude_id=lesson.id,
    )
    changes["starts_at"] = starts_at
    changes["ends_at"] = ends_at
    if changes.get("description") == "":
        changes["description"] = None
    if changes.get("join_url") == "":
        changes["join_url"] = None
    for field, value in changes.items():
        setattr(lesson, field, value)
    lesson.version += 1
    from app.modules.scheduling.models import RecurrenceExceptionAction
    from app.modules.scheduling.recurrence_service import mark_occurrence_exception

    mark_occurrence_exception(db, lesson, RecurrenceExceptionAction.MODIFIED)
    try:
        add_audit(db, teacher.id, "LESSON_UPDATED", "lesson", lesson.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise LessonConflictError("Время пересекается с другим запланированным уроком") from exc
    db.refresh(lesson)
    return lesson_response(lesson, profile)


def complete_lesson(db: Session, lesson_id: UUID, teacher: User) -> LessonResponse:
    lesson, profile = get_lesson_row(db, lesson_id, for_update=True)
    if lesson.status == LessonStatus.COMPLETED:
        return lesson_response(lesson, profile)
    if lesson.status == LessonStatus.CANCELLED:
        raise LessonStateError("Отменённый урок нельзя завершить")
    lesson.status = LessonStatus.COMPLETED
    lesson.completed_at = utc_now()
    lesson.version += 1
    add_audit(db, teacher.id, "LESSON_COMPLETED", "lesson", lesson.id)
    db.commit()
    db.refresh(lesson)
    return lesson_response(lesson, profile)


def cancel_lesson(db: Session, lesson_id: UUID, teacher: User) -> LessonResponse:
    lesson, profile = get_lesson_row(db, lesson_id, for_update=True)
    if lesson.status == LessonStatus.CANCELLED:
        return lesson_response(lesson, profile)
    if lesson.status == LessonStatus.COMPLETED:
        raise LessonStateError("Проведённый урок нельзя отменить")
    lesson.status = LessonStatus.CANCELLED
    lesson.version += 1
    from app.modules.scheduling.models import RecurrenceExceptionAction
    from app.modules.scheduling.recurrence_service import mark_occurrence_exception

    mark_occurrence_exception(db, lesson, RecurrenceExceptionAction.CANCELLED)
    add_audit(db, teacher.id, "LESSON_CANCELLED", "lesson", lesson.id)
    db.commit()
    db.refresh(lesson)
    return lesson_response(lesson, profile)


def next_student_lesson(db: Session, student_id: UUID) -> LessonResponse | None:
    row = db.execute(
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(
            Lesson.student_id == student_id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.ends_at > utc_now(),
        )
        .order_by(Lesson.starts_at)
        .limit(1)
    ).one_or_none()
    return lesson_response(*row) if row is not None else None


def today_teacher_lessons(db: Session, teacher_id: UUID, timezone: str) -> list[LessonResponse]:
    local_now = utc_now().astimezone(ZoneInfo(timezone))
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)
    rows = db.execute(
        select(Lesson, StudentProfile)
        .join(StudentProfile, StudentProfile.id == Lesson.student_id)
        .where(
            Lesson.teacher_id == teacher_id,
            Lesson.starts_at >= local_start.astimezone(UTC),
            Lesson.starts_at < local_end.astimezone(UTC),
        )
        .order_by(Lesson.starts_at)
    ).all()
    return [lesson_response(lesson, profile) for lesson, profile in rows]
