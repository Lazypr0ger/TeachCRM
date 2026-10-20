from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import (
    DbSession,
    StudentCsrfUser,
    StudentUser,
    TeacherCsrfUser,
    TeacherUser,
)
from app.modules.homework.schemas import (
    AssignmentCreateRequest,
    AssignmentUpdateRequest,
    HomeworkResponse,
    StudentHomeworkSummary,
    SubmissionCreateRequest,
    SubmissionResponse,
)
from app.modules.homework.service import (
    HomeworkConflictError,
    HomeworkNotFoundError,
    HomeworkValidationError,
    create_assignment,
    create_submission,
    get_homework,
    list_student_homework,
    update_assignment,
)

teacher_router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-homework"])
student_router = APIRouter(prefix="/api/v1/student", tags=["student-homework"])


def homework_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, HomeworkNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, HomeworkConflictError):
        code = status.HTTP_409_CONFLICT
    elif isinstance(exc, HomeworkValidationError):
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@teacher_router.get("/lessons/{lesson_id}/homework", response_model=HomeworkResponse)
def teacher_homework(lesson_id: UUID, teacher: TeacherUser, db: DbSession) -> HomeworkResponse:
    try:
        return get_homework(db, lesson_id, teacher)
    except HomeworkNotFoundError as exc:
        raise homework_http_error(exc) from exc


@teacher_router.get(
    "/students/{student_id}/homework", response_model=list[StudentHomeworkSummary]
)
def teacher_student_homework(
    student_id: UUID, teacher: TeacherUser, db: DbSession
) -> list[StudentHomeworkSummary]:
    try:
        return list_student_homework(db, student_id, teacher)
    except HomeworkNotFoundError as exc:
        raise homework_http_error(exc) from exc


@teacher_router.post(
    "/lessons/{lesson_id}/assignment",
    response_model=HomeworkResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_assignment(
    lesson_id: UUID,
    payload: AssignmentCreateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> HomeworkResponse:
    try:
        return create_assignment(db, lesson_id, payload, teacher)
    except (HomeworkNotFoundError, HomeworkConflictError) as exc:
        raise homework_http_error(exc) from exc


@teacher_router.patch("/assignments/{assignment_id}", response_model=HomeworkResponse)
def edit_assignment(
    assignment_id: UUID,
    payload: AssignmentUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> HomeworkResponse:
    try:
        return update_assignment(db, assignment_id, payload, teacher)
    except (HomeworkNotFoundError, HomeworkConflictError) as exc:
        raise homework_http_error(exc) from exc


@student_router.get("/lessons/{lesson_id}/homework", response_model=HomeworkResponse)
def student_homework(lesson_id: UUID, student: StudentUser, db: DbSession) -> HomeworkResponse:
    try:
        return get_homework(db, lesson_id, student)
    except HomeworkNotFoundError as exc:
        raise homework_http_error(exc) from exc


@student_router.post(
    "/assignments/{assignment_id}/submission",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_homework(
    assignment_id: UUID,
    payload: SubmissionCreateRequest,
    student: StudentCsrfUser,
    db: DbSession,
) -> SubmissionResponse:
    try:
        return create_submission(db, assignment_id, payload, student)
    except (HomeworkNotFoundError, HomeworkConflictError, HomeworkValidationError) as exc:
        raise homework_http_error(exc) from exc
