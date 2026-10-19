from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.billing.schemas import BillingProfileResponse, BillingProfileUpdateRequest
from app.modules.billing.service import (
    BillingProfileConflictError,
    BillingProfileNotFoundError,
    get_billing_profile,
    upsert_billing_profile,
)

router = APIRouter(prefix="/api/v1/teacher/students", tags=["teacher-billing"])


@router.get("/{student_id}/billing-profile", response_model=BillingProfileResponse)
def billing_profile(
    student_id: UUID, _teacher: TeacherUser, db: DbSession
) -> BillingProfileResponse:
    try:
        return get_billing_profile(db, student_id)
    except BillingProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{student_id}/billing-profile", response_model=BillingProfileResponse)
def edit_billing_profile(
    student_id: UUID,
    payload: BillingProfileUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> BillingProfileResponse:
    try:
        return upsert_billing_profile(db, student_id, payload, teacher)
    except BillingProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except BillingProfileConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
