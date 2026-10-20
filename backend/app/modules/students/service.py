from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.modules.auth.models import (
    InvitationToken,
    PasswordResetRequestRecord,
    PasswordResetToken,
    SessionRecord,
    StudentProfile,
    User,
    UserRole,
    UserStatus,
)
from app.modules.auth.service import add_audit, utc_now
from app.modules.billing.models import Invoice, Payment, PaymentClaim
from app.modules.files.models import FileLink, FileUploadTicket, StoredFile
from app.modules.files.storage import ObjectStorage
from app.modules.homework.models import HomeworkSubmission
from app.modules.lessons.models import Lesson
from app.modules.notifications.models import Notification
from app.modules.scheduling.models import RescheduleRequest, StudentAvailability
from app.modules.students.schemas import (
    OwnStudentProfile,
    OwnStudentProfileUpdate,
    StudentDetail,
    StudentSummary,
    StudentUpdateRequest,
)
from app.modules.trials.models import TrialRequest


class StudentNotFoundError(Exception):
    pass


class StudentAnonymizeError(Exception):
    pass


def model_data(item: Any) -> dict[str, Any]:
    return {column.key: getattr(item, column.key) for column in inspect(item).mapper.column_attrs}


def export_student_data(db: Session, student_id: UUID, actor: User) -> dict[str, Any]:
    profile, user = get_student(db, student_id)
    invoices = db.scalars(select(Invoice).where(Invoice.student_id == profile.id)).all()
    invoice_ids = [item.id for item in invoices]
    result = {
        "exported_at": utc_now(),
        "profile": {
            "id": profile.id,
            "login": user.login,
            "status": user.status,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "patronymic": profile.patronymic,
            "grade": profile.grade,
            "created_at": profile.created_at,
        },
        "lessons": [
            model_data(item)
            for item in db.scalars(select(Lesson).where(Lesson.student_id == profile.id))
        ],
        "availability": [
            model_data(item)
            for item in db.scalars(
                select(StudentAvailability).where(StudentAvailability.student_id == profile.id)
            )
        ],
        "reschedule_requests": [
            model_data(item)
            for item in db.scalars(
                select(RescheduleRequest).where(RescheduleRequest.student_id == profile.id)
            )
        ],
        "homework_submissions": [
            model_data(item)
            for item in db.scalars(
                select(HomeworkSubmission).where(HomeworkSubmission.student_id == profile.id)
            )
        ],
        "invoices": [model_data(item) for item in invoices],
        "payment_claims": (
            [
                model_data(item)
                for item in db.scalars(
                    select(PaymentClaim).where(PaymentClaim.invoice_id.in_(invoice_ids))
                )
            ]
            if invoice_ids
            else []
        ),
        "payments": [
            model_data(item)
            for item in db.scalars(select(Payment).where(Payment.student_id == profile.id))
        ],
        "files": [
            {key: value for key, value in model_data(item).items() if key != "storage_key"}
            for item in db.scalars(select(StoredFile).where(StoredFile.owner_user_id == user.id))
        ],
    }
    add_audit(db, actor.id, "STUDENT_DATA_EXPORTED", "student_profile", profile.id)
    db.commit()
    return result


def anonymize_student(
    db: Session,
    student_id: UUID,
    confirmation: str,
    actor: User,
    storage: ObjectStorage,
) -> None:
    row = db.execute(
        select(StudentProfile, User)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.id == student_id, User.role == UserRole.STUDENT)
        .with_for_update()
    ).one_or_none()
    if row is None:
        raise StudentNotFoundError
    profile, user = row
    if user.login.startswith("anonymized-"):
        raise StudentAnonymizeError("Ученик уже анонимизирован")
    if confirmation != user.login:
        raise StudentAnonymizeError("Введите текущий логин ученика для подтверждения")

    owned_files = db.scalars(select(StoredFile).where(StoredFile.owner_user_id == user.id)).all()
    owned_file_ids = [item.id for item in owned_files]
    tickets = db.scalars(
        select(FileUploadTicket).where(FileUploadTicket.owner_user_id == user.id)
    ).all()
    for stored_file in owned_files:
        storage.delete(stored_file.storage_key)
    for ticket in tickets:
        storage.delete(ticket.storage_key)
    if owned_file_ids:
        db.execute(delete(FileLink).where(FileLink.file_id.in_(owned_file_ids)))
    db.execute(delete(FileUploadTicket).where(FileUploadTicket.owner_user_id == user.id))
    if owned_file_ids:
        db.execute(delete(StoredFile).where(StoredFile.id.in_(owned_file_ids)))

    invoice_ids = db.scalars(select(Invoice.id).where(Invoice.student_id == profile.id)).all()
    db.execute(delete(Notification).where(Notification.recipient_user_id == user.id))
    db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
    db.execute(delete(InvitationToken).where(InvitationToken.user_id == user.id))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    db.execute(
        delete(PasswordResetRequestRecord).where(PasswordResetRequestRecord.user_id == user.id)
    )
    submissions = db.scalars(
        select(HomeworkSubmission).where(HomeworkSubmission.student_id == profile.id)
    ).all()
    for submission in submissions:
        submission.answer_text = None
        submission.idempotency_key = f"anonymized-{submission.id}"
    db.execute(
        update(RescheduleRequest)
        .where(RescheduleRequest.student_id == profile.id)
        .values(reason=None, response_note=None)
    )
    if invoice_ids:
        db.execute(
            update(PaymentClaim)
            .where(PaymentClaim.invoice_id.in_(invoice_ids))
            .values(comment=None, rejection_reason=None)
        )
    db.execute(
        update(TrialRequest)
        .where(TrialRequest.converted_student_id == profile.id)
        .values(name="Удалённый ученик", goal=None, comment=None, contact_normalized=None)
    )
    user.login = f"anonymized-{user.id}"
    user.password_hash = None
    user.status = UserStatus.SUSPENDED
    user.version += 1
    profile.first_name = "Ученик"
    profile.last_name = "Удалённый"
    profile.patronymic = None
    profile.grade = None
    profile.active = False
    add_audit(db, actor.id, "STUDENT_ANONYMIZED", "student_profile", profile.id)
    db.commit()


def to_summary(profile: StudentProfile, user: User) -> StudentSummary:
    return StudentSummary(
        id=profile.id,
        user_id=user.id,
        login=user.login,
        status=user.status,
        first_name=profile.first_name,
        last_name=profile.last_name,
        patronymic=profile.patronymic,
        grade=profile.grade,
        created_at=profile.created_at,
    )


def list_students(
    db: Session,
    *,
    search: str | None,
    grade: int | None,
    student_status: str | None,
    sort: str,
    page: int,
    page_size: int,
) -> tuple[list[StudentSummary], int]:
    filters = [User.role == UserRole.STUDENT]
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        filters.append(
            or_(
                StudentProfile.first_name.ilike(pattern),
                StudentProfile.last_name.ilike(pattern),
                StudentProfile.patronymic.ilike(pattern),
                User.login.ilike(pattern),
            )
        )
    if grade is not None:
        filters.append(StudentProfile.grade == grade)
    if student_status is not None:
        filters.append(User.status == student_status)

    base = (
        select(StudentProfile, User).join(User, User.id == StudentProfile.user_id).where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    order = {
        "created_desc": (StudentProfile.created_at.desc(), StudentProfile.id),
        "created_asc": (StudentProfile.created_at, StudentProfile.id),
        "name": (StudentProfile.last_name, StudentProfile.first_name, StudentProfile.id),
    }[sort]
    rows = db.execute(base.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return [to_summary(profile, user) for profile, user in rows], total


def get_student(db: Session, student_id: UUID) -> tuple[StudentProfile, User]:
    row = db.execute(
        select(StudentProfile, User)
        .join(User, User.id == StudentProfile.user_id)
        .where(StudentProfile.id == student_id, User.role == UserRole.STUDENT)
    ).one_or_none()
    if row is None:
        raise StudentNotFoundError
    return row


def student_detail(profile: StudentProfile, user: User) -> StudentDetail:
    return StudentDetail(
        **to_summary(profile, user).model_dump(),
        activated_at=user.activated_at,
        last_login_at=user.last_login_at,
        updated_at=profile.updated_at,
    )


def update_student(
    db: Session, student_id: UUID, payload: StudentUpdateRequest, actor: User
) -> StudentDetail:
    profile, user = get_student(db, student_id)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name", "patronymic"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip()
    for field, value in changes.items():
        if field == "patronymic" and value == "":
            value = None
        setattr(profile, field, value)
    add_audit(db, actor.id, "STUDENT_UPDATED", "student_profile", profile.id)
    db.commit()
    db.refresh(profile)
    return student_detail(profile, user)


def own_profile(db: Session, user: User, *, for_update: bool = False) -> StudentProfile:
    query = select(StudentProfile).where(StudentProfile.user_id == user.id)
    if for_update:
        query = query.with_for_update()
    profile = db.scalar(query)
    if profile is None:
        raise StudentNotFoundError
    return profile


def own_profile_response(profile: StudentProfile) -> OwnStudentProfile:
    return OwnStudentProfile(
        id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        patronymic=profile.patronymic,
        grade=profile.grade,
        updated_at=profile.updated_at,
    )


def update_own_profile(
    db: Session,
    payload: OwnStudentProfileUpdate,
    user: User,
) -> OwnStudentProfile:
    profile = own_profile(db, user, for_update=True)
    changes = payload.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name", "patronymic"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip()
    for field, value in changes.items():
        setattr(profile, field, None if field == "patronymic" and value == "" else value)
    add_audit(db, user.id, "STUDENT_PROFILE_UPDATED", "student_profile", profile.id)
    db.commit()
    db.refresh(profile)
    return own_profile_response(profile)
