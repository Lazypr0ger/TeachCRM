from uuid import UUID

from fastapi import APIRouter

from app.modules.auth.dependencies import DbSession, StudentUser, TeacherUser
from app.modules.billing.schemas import BillingSummaryResponse, InvoiceListResponse
from app.modules.billing.service import list_invoices, student_billing_summary
from app.modules.lessons.service import student_profile_for_user

teacher_router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-invoices"])
student_router = APIRouter(prefix="/api/v1/student", tags=["student-billing"])


@teacher_router.get("/invoices", response_model=InvoiceListResponse)
def teacher_invoices(
    _teacher: TeacherUser, db: DbSession, student_id: UUID | None = None
) -> InvoiceListResponse:
    return list_invoices(db, student_id=student_id)


@student_router.get("/invoices", response_model=InvoiceListResponse)
def student_invoices(student: StudentUser, db: DbSession) -> InvoiceListResponse:
    profile = student_profile_for_user(db, student.id)
    return list_invoices(db, student_id=profile.id)


@student_router.get("/billing", response_model=BillingSummaryResponse)
def student_billing(student: StudentUser, db: DbSession) -> BillingSummaryResponse:
    return student_billing_summary(db, student)
