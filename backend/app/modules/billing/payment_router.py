from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import (
    DbSession,
    StudentCsrfUser,
    StudentUser,
    TeacherCsrfUser,
    TeacherUser,
)
from app.modules.billing.schemas import (
    PaymentClaimConfirmRequest,
    PaymentClaimCreateRequest,
    PaymentClaimRejectRequest,
    PaymentClaimResponse,
    PaymentResponse,
)
from app.modules.billing.service import (
    InvoiceNotFoundError,
    InvoiceValidationError,
    PaymentClaimConflictError,
    confirm_payment_claim,
    create_payment_claim,
    list_payment_claims,
    list_payments,
    reject_payment_claim,
)

student_router = APIRouter(prefix="/api/v1/student", tags=["student-payment-claims"])
teacher_router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-payment-claims"])


def claim_error(exc: Exception) -> HTTPException:
    if isinstance(exc, InvoiceNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, PaymentClaimConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


@student_router.post(
    "/invoices/{invoice_id}/payment-claims",
    response_model=PaymentClaimResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_claim(
    invoice_id: UUID,
    payload: PaymentClaimCreateRequest,
    student: StudentCsrfUser,
    db: DbSession,
) -> PaymentClaimResponse:
    try:
        return create_payment_claim(db, invoice_id, payload, student)
    except (InvoiceNotFoundError, InvoiceValidationError, PaymentClaimConflictError) as exc:
        raise claim_error(exc) from exc


@student_router.get("/payment-claims", response_model=list[PaymentClaimResponse])
def student_claims(student: StudentUser, db: DbSession) -> list[PaymentClaimResponse]:
    return list_payment_claims(db, student_user_id=student.id)


@teacher_router.get("/payment-claims", response_model=list[PaymentClaimResponse])
def teacher_claims(
    _teacher: TeacherUser,
    db: DbSession,
    claim_status: Literal["PENDING", "CONFIRMED", "REJECTED"] | None = None,
) -> list[PaymentClaimResponse]:
    return list_payment_claims(db, claim_status=claim_status)


@teacher_router.post("/payment-claims/{claim_id}/confirm", response_model=PaymentResponse)
def confirm_claim(
    claim_id: UUID,
    payload: PaymentClaimConfirmRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> PaymentResponse:
    try:
        return confirm_payment_claim(db, claim_id, payload, teacher)
    except (InvoiceNotFoundError, InvoiceValidationError, PaymentClaimConflictError) as exc:
        raise claim_error(exc) from exc


@teacher_router.post("/payment-claims/{claim_id}/reject", response_model=PaymentClaimResponse)
def reject_claim(
    claim_id: UUID,
    payload: PaymentClaimRejectRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> PaymentClaimResponse:
    try:
        return reject_payment_claim(db, claim_id, payload, teacher)
    except (InvoiceNotFoundError, PaymentClaimConflictError) as exc:
        raise claim_error(exc) from exc


@teacher_router.get("/payments", response_model=list[PaymentResponse])
def payments(
    _teacher: TeacherUser, db: DbSession, student_id: UUID | None = None
) -> list[PaymentResponse]:
    return list_payments(db, student_id=student_id)
