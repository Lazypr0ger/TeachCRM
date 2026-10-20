import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.models import (
    InvitationToken,
    SessionRecord,
    StudentProfile,
    User,
    UserRole,
    UserStatus,
)
from app.modules.auth.security import new_token, normalize_login, token_hash
from app.modules.auth.service import add_audit, expired, utc_now
from app.modules.lessons.models import Lesson, LessonStatus
from app.modules.scheduling.service import AvailabilityConflictError, ensure_teacher_available
from app.modules.trials.models import TrialRequest, TrialStatus, TrialSubmissionAttempt
from app.modules.trials.schemas import (
    TrialConversionResponse,
    TrialConvertRequest,
    TrialCreateRequest,
    TrialPage,
    TrialResponse,
    TrialUpdateRequest,
)


class TrialError(Exception):
    pass


class TrialNotFoundError(TrialError):
    pass


class TrialConflictError(TrialError):
    pass


class TrialRateLimitError(TrialError):
    pass


@dataclass(frozen=True)
class TrialIntake:
    name: str
    grade: int
    goal: str | None
    preferred_start: datetime | None
    preferred_end: datetime | None
    comment: str | None
    source: str


def web_intake(payload: TrialCreateRequest) -> TrialIntake:
    return TrialIntake(
        name=payload.name,
        grade=payload.grade,
        goal=payload.goal,
        preferred_start=payload.preferred_start,
        preferred_end=payload.preferred_end,
        comment=payload.comment,
        source="WEB",
    )


def normalize_time(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


def has_active_session(db: Session, raw_token: str | None) -> bool:
    if not raw_token:
        return False
    record = db.scalar(
        select(SessionRecord).where(SessionRecord.token_hash == token_hash(raw_token))
    )
    now = utc_now()
    if (
        record is None
        or record.revoked_at is not None
        or expired(record.expires_at, now)
        or expired(record.idle_expires_at, now)
    ):
        return False
    user = db.get(User, record.user_id)
    return user is not None and user.status == UserStatus.ACTIVE


def split_name(name: str) -> tuple[str, str, str | None]:
    parts = name.split()
    return parts[0], parts[1], parts[2] if len(parts) == 3 else None


def possible_existing_student(db: Session, name: str, grade: int) -> bool:
    last_name, first_name, patronymic = split_name(name)
    query = select(StudentProfile.id).where(
        func.lower(StudentProfile.last_name) == last_name.lower(),
        func.lower(StudentProfile.first_name) == first_name.lower(),
        StudentProfile.grade == grade,
    )
    if patronymic is None:
        query = query.where(StudentProfile.patronymic.is_(None))
    else:
        query = query.where(func.lower(StudentProfile.patronymic) == patronymic.lower())
    return db.scalar(query.limit(1)) is not None


def trial_response(item: TrialRequest) -> TrialResponse:
    return TrialResponse(
        id=item.id,
        name=item.name,
        grade=item.grade,
        goal=item.goal,
        preferred_start=item.preferred_start,
        preferred_end=item.preferred_end,
        confirmed_start=item.confirmed_start,
        confirmed_end=item.confirmed_end,
        comment=item.comment,
        source=item.source,
        status=item.status,
        possible_existing_student=item.possible_existing_student,
        converted_student_id=item.converted_student_id,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def create_trial_request(
    db: Session,
    intake: TrialIntake,
    *,
    client_hash: str,
) -> TrialRequest:
    now = utc_now()
    attempts = db.scalar(
        select(func.count())
        .select_from(TrialSubmissionAttempt)
        .where(
            TrialSubmissionAttempt.client_hash == client_hash,
            TrialSubmissionAttempt.created_at >= now - timedelta(hours=1),
        )
    )
    if attempts is not None and attempts >= 5:
        raise TrialRateLimitError("Слишком много заявок. Повторите позже")
    db.add(TrialSubmissionAttempt(client_hash=client_hash, created_at=now))
    teacher_id = db.scalar(select(User.id).where(User.role == UserRole.TEACHER))
    if teacher_id is None:
        raise TrialConflictError("Приём заявок временно недоступен")
    item = TrialRequest(
        name=intake.name,
        grade=intake.grade,
        goal=intake.goal,
        contact_method=None,
        contact_normalized=None,
        preferred_start=normalize_time(intake.preferred_start),
        preferred_end=normalize_time(intake.preferred_end),
        confirmed_start=None,
        confirmed_end=None,
        comment=intake.comment,
        source=intake.source,
        status=TrialStatus.NEW,
        possible_existing_student=possible_existing_student(db, intake.name, intake.grade),
        teacher_id=None,
        converted_student_id=None,
        version=1,
    )
    db.add(item)
    db.flush()
    add_audit(db, None, "TRIAL_RECEIVED", "trial_request", item.id)
    from app.modules.notifications.service import enqueue_notification

    enqueue_notification(
        db,
        event_type="TRIAL_RECEIVED",
        aggregate_id=item.id,
        recipient_user_id=teacher_id,
        title="Новая заявка на пробное занятие",
        body="Откройте раздел пробных заявок, чтобы проверить запрос.",
        target_type="TRIAL_REQUEST",
        target_id=item.id,
    )
    db.commit()
    db.refresh(item)
    return item


def list_trial_requests(
    db: Session,
    *,
    request_status: str | None,
    page: int,
    page_size: int,
) -> TrialPage:
    filters = [TrialRequest.status == request_status] if request_status else []
    total = db.scalar(select(func.count(TrialRequest.id)).where(*filters)) or 0
    items = db.scalars(
        select(TrialRequest)
        .where(*filters)
        .order_by(TrialRequest.created_at.desc(), TrialRequest.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TrialPage(
        items=[trial_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


TRANSITIONS: dict[str, set[str]] = {
    TrialStatus.NEW: {
        TrialStatus.IN_REVIEW,
        TrialStatus.RESCHEDULE_REQUESTED,
        TrialStatus.CONFIRMED,
        TrialStatus.REJECTED,
        TrialStatus.CANCELLED,
    },
    TrialStatus.IN_REVIEW: {
        TrialStatus.RESCHEDULE_REQUESTED,
        TrialStatus.CONFIRMED,
        TrialStatus.REJECTED,
        TrialStatus.CANCELLED,
    },
    TrialStatus.RESCHEDULE_REQUESTED: {
        TrialStatus.IN_REVIEW,
        TrialStatus.CONFIRMED,
        TrialStatus.REJECTED,
        TrialStatus.CANCELLED,
    },
    TrialStatus.CONFIRMED: {
        TrialStatus.CONFIRMED,
        TrialStatus.COMPLETED,
        TrialStatus.CANCELLED,
    },
    TrialStatus.COMPLETED: set(),
    TrialStatus.REJECTED: set(),
    TrialStatus.CANCELLED: set(),
}


def ensure_trial_slot(
    db: Session,
    *,
    teacher: User,
    trial_id: UUID,
    starts_at: datetime,
    ends_at: datetime,
) -> None:
    db.scalar(select(User.id).where(User.id == teacher.id).with_for_update())
    try:
        ensure_teacher_available(db, teacher.id, starts_at, ends_at)
    except AvailabilityConflictError as exc:
        raise TrialConflictError(str(exc)) from exc
    lesson_conflict = db.scalar(
        select(Lesson.id).where(
            Lesson.teacher_id == teacher.id,
            Lesson.status == LessonStatus.SCHEDULED,
            Lesson.starts_at < ends_at,
            Lesson.ends_at > starts_at,
        )
    )
    trial_conflict = db.scalar(
        select(TrialRequest.id).where(
            TrialRequest.id != trial_id,
            TrialRequest.teacher_id == teacher.id,
            TrialRequest.status == TrialStatus.CONFIRMED,
            TrialRequest.confirmed_start < ends_at,
            TrialRequest.confirmed_end > starts_at,
        )
    )
    if lesson_conflict is not None or trial_conflict is not None:
        raise TrialConflictError("Время пересекается с другим занятием")


def update_trial_request(
    db: Session,
    trial_id: UUID,
    payload: TrialUpdateRequest,
    teacher: User,
) -> TrialResponse:
    item = db.scalar(select(TrialRequest).where(TrialRequest.id == trial_id).with_for_update())
    if item is None:
        raise TrialNotFoundError("Заявка не найдена")
    if item.version != payload.version:
        raise TrialConflictError("Заявка уже изменена в другой вкладке")
    if payload.status not in TRANSITIONS[item.status]:
        raise TrialConflictError("Недопустимый переход статуса")
    if payload.status == TrialStatus.CONFIRMED:
        assert payload.confirmed_start is not None and payload.confirmed_end is not None
        starts_at = normalize_time(payload.confirmed_start)
        ends_at = normalize_time(payload.confirmed_end)
        assert starts_at is not None and ends_at is not None
        if starts_at <= utc_now():
            raise TrialConflictError("Пробное занятие должно быть в будущем")
        ensure_trial_slot(
            db,
            teacher=teacher,
            trial_id=item.id,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        item.confirmed_start = starts_at
        item.confirmed_end = ends_at
        item.teacher_id = teacher.id
    item.status = payload.status
    item.version += 1
    add_audit(db, teacher.id, "TRIAL_STATUS_UPDATED", "trial_request", item.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TrialConflictError("Время пересекается с другим пробным занятием") from exc
    db.refresh(item)
    return trial_response(item)


def convert_trial_request(
    db: Session,
    trial_id: UUID,
    payload: TrialConvertRequest,
    teacher: User,
    settings: Settings,
) -> TrialConversionResponse:
    item = db.scalar(select(TrialRequest).where(TrialRequest.id == trial_id).with_for_update())
    if item is None:
        raise TrialNotFoundError("Заявка не найдена")
    if item.converted_student_id is not None:
        profile = db.get(StudentProfile, item.converted_student_id)
        user = db.get(User, profile.user_id) if profile else None
        if profile is None or user is None:
            raise TrialConflictError("Связанный ученик не найден")
        return TrialConversionResponse(
            student_id=profile.id,
            login=user.login,
            created=False,
            activation_url=None,
            expires_at=None,
        )
    if item.status != TrialStatus.COMPLETED:
        raise TrialConflictError("Создать ученика можно после завершения пробного занятия")
    login = normalize_login(payload.login or f"student-{secrets.token_hex(4)}")
    if db.scalar(select(User.id).where(func.lower(User.login) == login)) is not None:
        raise TrialConflictError("Логин уже используется")
    last_name, first_name, patronymic = split_name(item.name)
    user = User(role=UserRole.STUDENT, login=login, status=UserStatus.INVITED)
    db.add(user)
    db.flush()
    profile = StudentProfile(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        patronymic=patronymic,
        grade=item.grade,
        active=True,
    )
    db.add(profile)
    db.flush()
    raw_token = new_token()
    expires_at = utc_now() + timedelta(hours=settings.invitation_ttl_hours)
    db.add(
        InvitationToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=expires_at,
            created_at=utc_now(),
        )
    )
    item.converted_student_id = profile.id
    item.version += 1
    add_audit(db, teacher.id, "TRIAL_CONVERTED", "trial_request", item.id)
    add_audit(db, teacher.id, "STUDENT_CREATED", "student_profile", profile.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise TrialConflictError("Не удалось создать ученика") from exc
    return TrialConversionResponse(
        student_id=profile.id,
        login=user.login,
        created=True,
        activation_url=f"{settings.app_base_url}/activate?token={raw_token}",
        expires_at=expires_at.isoformat(),
    )
