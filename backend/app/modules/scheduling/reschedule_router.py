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
from app.modules.scheduling.reschedule_schemas import (
    RescheduleCounterRequest,
    RescheduleCreateRequest,
    RescheduleDecisionRequest,
    RescheduleResponse,
)
from app.modules.scheduling.reschedule_service import (
    RescheduleConflictError,
    RescheduleNotFoundError,
    create_request,
    list_student_requests,
    list_teacher_requests,
    student_accept_counter,
    student_cancel,
    teacher_accept,
    teacher_counter,
    teacher_reject,
)

student_router = APIRouter(prefix="/api/v1/student", tags=["student-reschedule"])
teacher_router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-reschedule"])


def reschedule_http_error(exc: Exception) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, RescheduleNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(exc))


@student_router.post(
    "/lessons/{lesson_id}/reschedule-requests",
    response_model=RescheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_reschedule(
    lesson_id: UUID,
    payload: RescheduleCreateRequest,
    student: StudentCsrfUser,
    db: DbSession,
) -> RescheduleResponse:
    try:
        return create_request(db, lesson_id, payload, student)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc


@student_router.get("/reschedule-requests", response_model=list[RescheduleResponse])
def student_requests(student: StudentUser, db: DbSession) -> list[RescheduleResponse]:
    return list_student_requests(db, student)


@student_router.post(
    "/reschedule-requests/{request_id}/accept-counter",
    response_model=RescheduleResponse,
)
def accept_counter(request_id: UUID, student: StudentCsrfUser, db: DbSession) -> RescheduleResponse:
    try:
        return student_accept_counter(db, request_id, student)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc


@student_router.post("/reschedule-requests/{request_id}/cancel", response_model=RescheduleResponse)
def cancel_request(request_id: UUID, student: StudentCsrfUser, db: DbSession) -> RescheduleResponse:
    try:
        return student_cancel(db, request_id, student)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc


@teacher_router.get("/reschedule-requests", response_model=list[RescheduleResponse])
def teacher_requests(
    _teacher: TeacherUser,
    db: DbSession,
    request_status: Literal["PENDING", "COUNTER_OFFER", "ACCEPTED", "REJECTED", "CANCELLED"]
    | None = None,
) -> list[RescheduleResponse]:
    return list_teacher_requests(db, request_status)


@teacher_router.post("/reschedule-requests/{request_id}/accept", response_model=RescheduleResponse)
def accept_request(request_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> RescheduleResponse:
    try:
        return teacher_accept(db, request_id, teacher)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc


@teacher_router.post("/reschedule-requests/{request_id}/reject", response_model=RescheduleResponse)
def reject_request(
    request_id: UUID,
    payload: RescheduleDecisionRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> RescheduleResponse:
    try:
        return teacher_reject(db, request_id, payload, teacher)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc


@teacher_router.post("/reschedule-requests/{request_id}/counter", response_model=RescheduleResponse)
def counter_request(
    request_id: UUID,
    payload: RescheduleCounterRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> RescheduleResponse:
    try:
        return teacher_counter(db, request_id, payload, teacher)
    except (RescheduleNotFoundError, RescheduleConflictError) as exc:
        raise reschedule_http_error(exc) from exc
