from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, StudentUser, TeacherCsrfUser, TeacherUser
from app.modules.billing.schemas import (
    BillingSummaryResponse,
    InvoiceAdjustmentRequest,
    InvoiceListResponse,
    InvoiceResponse,
    MonthlyInvoiceCreateRequest,
)
from app.modules.billing.service import (
    BillingProfileNotFoundError,
    InvoiceNotFoundError,
    InvoiceValidationError,
    add_invoice_adjustment,
    create_monthly_invoice,
    finance_summary,
    list_invoices,
    student_billing_summary,
)
from app.modules.lessons.service import student_profile_for_user

teacher_router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-invoices"])
student_router = APIRouter(prefix="/api/v1/student", tags=["student-billing"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@teacher_router.get("/invoices", response_model=InvoiceListResponse)
def teacher_invoices(
    _teacher: TeacherUser, db: DbSession, student_id: UUID | None = None
) -> InvoiceListResponse:
    return list_invoices(db, student_id=student_id)


@teacher_router.get("/finances/summary", response_model=BillingSummaryResponse)
def teacher_summary(
    _teacher: TeacherUser, db: DbSession, student_id: UUID | None = None
) -> BillingSummaryResponse:
    return finance_summary(db, student_id=student_id)


@student_router.get("/invoices", response_model=InvoiceListResponse)
def student_invoices(student: StudentUser, db: DbSession) -> InvoiceListResponse:
    profile = student_profile_for_user(db, student.id)
    return list_invoices(db, student_id=profile.id)


@student_router.get("/billing", response_model=BillingSummaryResponse)
def student_billing(student: StudentUser, db: DbSession) -> BillingSummaryResponse:
    return student_billing_summary(db, student)


@teacher_router.post("/invoices/monthly", response_model=InvoiceResponse)
def add_monthly_invoice(
    payload: MonthlyInvoiceCreateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> InvoiceResponse:
    try:
        return create_monthly_invoice(
            db,
            student_id=payload.student_id,
            year=payload.year,
            month=payload.month,
            actor=teacher,
            timezone=settings.app_timezone,
        )
    except BillingProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvoiceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc


@teacher_router.post("/invoices/{invoice_id}/adjustments", response_model=InvoiceResponse)
def adjust_invoice(
    invoice_id: UUID,
    payload: InvoiceAdjustmentRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> InvoiceResponse:
    try:
        return add_invoice_adjustment(db, invoice_id, payload, teacher)
    except InvoiceNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvoiceValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
