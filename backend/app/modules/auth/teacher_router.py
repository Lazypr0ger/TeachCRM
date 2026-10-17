from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.auth.models import (
    PasswordResetRequestRecord,
    StudentProfile,
    User,
    UserRole,
    UserStatus,
)
from app.modules.auth.schemas import (
    InvitationResponse,
    MessageResponse,
    ResetLinkResponse,
    ResetRequestResponse,
    StudentCreateRequest,
)
from app.modules.auth.service import (
    AuthError,
    create_student_with_invitation,
    issue_invitation,
    issue_password_reset,
    suspend_student,
)

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-auth"])
AppSettings = Annotated[Settings, Depends(get_settings)]


def invitation_response(
    profile: StudentProfile, user: User, raw: str, expires_at: datetime, settings: Settings
) -> InvitationResponse:
    return InvitationResponse(
        student_id=profile.id,
        user_id=user.id,
        login=user.login,
        activation_token=raw,
        activation_url=f"{settings.app_base_url}/activate?token={raw}",
        expires_at=expires_at.isoformat(),
    )


@router.post("/students", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> InvitationResponse:
    try:
        profile, user, raw, expires_at = create_student_with_invitation(
            db, payload, teacher, settings
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return invitation_response(profile, user, raw, expires_at, settings)


@router.post("/students/{student_id}/invite", response_model=InvitationResponse)
def renew_invitation(
    student_id: UUID,
    _teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> InvitationResponse:
    profile = db.get(StudentProfile, student_id)
    user = db.get(User, profile.user_id) if profile else None
    if profile is None or user is None or user.status != UserStatus.INVITED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден")
    raw, expires_at = issue_invitation(db, user.id, settings)
    return invitation_response(profile, user, raw, expires_at, settings)


@router.post("/students/{student_id}/password-reset", response_model=ResetLinkResponse)
def student_reset_link(
    student_id: UUID,
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> ResetLinkResponse:
    profile = db.get(StudentProfile, student_id)
    user = db.get(User, profile.user_id) if profile else None
    if profile is None or user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден")
    raw, expires_at = issue_password_reset(db, user, teacher, settings)
    return ResetLinkResponse(
        reset_token=raw,
        reset_url=f"{settings.app_base_url}/reset-password?token={raw}",
        expires_at=expires_at.isoformat(),
    )


@router.post("/students/{student_id}/suspend", response_model=MessageResponse)
def suspend(
    student_id: UUID,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> MessageResponse:
    try:
        suspend_student(db, student_id, teacher)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MessageResponse(message="Аккаунт ученика заблокирован")


@router.post("/account/password-reset", response_model=ResetLinkResponse)
def teacher_reset_link(
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> ResetLinkResponse:
    if teacher.role != UserRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    raw, expires_at = issue_password_reset(db, teacher, teacher, settings)
    return ResetLinkResponse(
        reset_token=raw,
        reset_url=f"{settings.app_base_url}/reset-password?token={raw}",
        expires_at=expires_at.isoformat(),
    )


@router.get("/password-reset-requests", response_model=list[ResetRequestResponse])
def password_reset_requests(_teacher: TeacherUser, db: DbSession) -> list[ResetRequestResponse]:
    rows = db.execute(
        select(PasswordResetRequestRecord, User)
        .join(User, User.id == PasswordResetRequestRecord.user_id)
        .where(PasswordResetRequestRecord.resolved_at.is_(None))
        .order_by(PasswordResetRequestRecord.requested_at)
    ).all()
    return [
        ResetRequestResponse(
            id=request.id,
            user_id=user.id,
            login=user.login,
            role=user.role,
            requested_at=request.requested_at.isoformat(),
        )
        for request, user in rows
    ]
