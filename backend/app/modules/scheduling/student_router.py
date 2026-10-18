from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.modules.auth.dependencies import DbSession, StudentCsrfUser, StudentUser
from app.modules.lessons.service import list_lessons, student_profile_for_user
from app.modules.scheduling.schemas import (
    StudentAvailabilityRequest,
    StudentAvailabilityResponse,
    StudentScheduleResponse,
)
from app.modules.scheduling.service import (
    AvailabilityConflictError,
    AvailabilityNotFoundError,
    create_student_mark,
    delete_student_mark,
    list_student_availability,
    update_student_mark,
)

router = APIRouter(prefix="/api/v1/student", tags=["student-schedule"])


def availability_http_error(exc: Exception) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, AvailabilityNotFoundError)
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/schedule", response_model=StudentScheduleResponse)
def schedule(student: StudentUser, db: DbSession) -> StudentScheduleResponse:
    profile = student_profile_for_user(db, student.id)
    lessons, _total = list_lessons(
        db,
        student_id=profile.id,
        lesson_status=None,
        date_from=None,
        date_to=None,
        page=1,
        page_size=100,
    )
    return StudentScheduleResponse(
        lessons=lessons, availability=list_student_availability(db, profile.id)
    )


@router.post(
    "/availability",
    response_model=StudentAvailabilityResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_availability(
    payload: StudentAvailabilityRequest, student: StudentCsrfUser, db: DbSession
) -> StudentAvailabilityResponse:
    profile = student_profile_for_user(db, student.id)
    try:
        return create_student_mark(db, profile, payload, student)
    except AvailabilityConflictError as exc:
        raise availability_http_error(exc) from exc


@router.patch("/availability/{item_id}", response_model=StudentAvailabilityResponse)
def edit_availability(
    item_id: UUID,
    payload: StudentAvailabilityRequest,
    student: StudentCsrfUser,
    db: DbSession,
) -> StudentAvailabilityResponse:
    profile = student_profile_for_user(db, student.id)
    try:
        return update_student_mark(db, profile, item_id, payload, student)
    except (AvailabilityNotFoundError, AvailabilityConflictError) as exc:
        raise availability_http_error(exc) from exc


@router.delete("/availability/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_availability(item_id: UUID, student: StudentCsrfUser, db: DbSession) -> Response:
    profile = student_profile_for_user(db, student.id)
    try:
        delete_student_mark(db, profile, item_id, student)
    except AvailabilityNotFoundError as exc:
        raise availability_http_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
