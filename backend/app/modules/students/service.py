from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.modules.auth.models import StudentProfile, User, UserRole
from app.modules.auth.service import add_audit
from app.modules.students.schemas import (
    OwnStudentProfile,
    OwnStudentProfileUpdate,
    StudentDetail,
    StudentSummary,
    StudentUpdateRequest,
)


class StudentNotFoundError(Exception):
    pass


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
        select(StudentProfile, User)
        .join(User, User.id == StudentProfile.user_id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    order = {
        "created_desc": (StudentProfile.created_at.desc(), StudentProfile.id),
        "created_asc": (StudentProfile.created_at, StudentProfile.id),
        "name": (StudentProfile.last_name, StudentProfile.first_name, StudentProfile.id),
    }[sort]
    rows = db.execute(
        base.order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
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
