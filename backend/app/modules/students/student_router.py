from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import DbSession, StudentCsrfUser, StudentUser
from app.modules.students.schemas import OwnStudentProfile, OwnStudentProfileUpdate
from app.modules.students.service import (
    StudentNotFoundError,
    own_profile,
    own_profile_response,
    update_own_profile,
)

router = APIRouter(prefix="/api/v1/student/profile", tags=["student-profile"])


@router.get("", response_model=OwnStudentProfile)
def profile(student: StudentUser, db: DbSession) -> OwnStudentProfile:
    try:
        return own_profile_response(own_profile(db, student))
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не найден"
        ) from exc


@router.patch("", response_model=OwnStudentProfile)
def edit_profile(
    payload: OwnStudentProfileUpdate,
    student: StudentCsrfUser,
    db: DbSession,
) -> OwnStudentProfile:
    try:
        return update_own_profile(db, payload, student)
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не найден"
        ) from exc
