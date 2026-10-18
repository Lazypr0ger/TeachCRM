from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.lessons.schemas import (
    LessonCreateRequest,
    LessonListResponse,
    LessonResponse,
    LessonUpdateRequest,
)
from app.modules.lessons.service import (
    LessonConflictError,
    LessonNotFoundError,
    LessonStateError,
    LessonVersionError,
    cancel_lesson,
    complete_lesson,
    create_lesson,
    get_lesson_row,
    lesson_response,
    list_lessons,
    update_lesson,
)

router = APIRouter(prefix="/api/v1/teacher/lessons", tags=["teacher-lessons"])


def lesson_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LessonNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (LessonConflictError, LessonStateError, LessonVersionError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректный урок")


@router.get("", response_model=LessonListResponse)
def lessons(
    _teacher: TeacherUser,
    db: DbSession,
    student_id: UUID | None = None,
    lesson_status: Literal["SCHEDULED", "COMPLETED", "CANCELLED"] | None = None,
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> LessonListResponse:
    items, total = list_lessons(
        db,
        student_id=student_id,
        lesson_status=lesson_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return LessonListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
def add_lesson(
    payload: LessonCreateRequest, teacher: TeacherCsrfUser, db: DbSession
) -> LessonResponse:
    try:
        return create_lesson(db, payload, teacher)
    except (LessonConflictError, LessonNotFoundError) as exc:
        raise lesson_http_error(exc) from exc


@router.get("/{lesson_id}", response_model=LessonResponse)
def lesson(lesson_id: UUID, _teacher: TeacherUser, db: DbSession) -> LessonResponse:
    try:
        record, profile = get_lesson_row(db, lesson_id)
    except LessonNotFoundError as exc:
        raise lesson_http_error(exc) from exc
    return lesson_response(record, profile)


@router.patch("/{lesson_id}", response_model=LessonResponse)
def edit_lesson(
    lesson_id: UUID,
    payload: LessonUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> LessonResponse:
    try:
        return update_lesson(db, lesson_id, payload, teacher)
    except (LessonNotFoundError, LessonConflictError, LessonStateError, LessonVersionError) as exc:
        raise lesson_http_error(exc) from exc


@router.post("/{lesson_id}/complete", response_model=LessonResponse)
def complete(lesson_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> LessonResponse:
    try:
        return complete_lesson(db, lesson_id, teacher)
    except (LessonNotFoundError, LessonStateError) as exc:
        raise lesson_http_error(exc) from exc


@router.post("/{lesson_id}/cancel", response_model=LessonResponse)
def cancel(lesson_id: UUID, teacher: TeacherCsrfUser, db: DbSession) -> LessonResponse:
    try:
        return cancel_lesson(db, lesson_id, teacher)
    except (LessonNotFoundError, LessonStateError) as exc:
        raise lesson_http_error(exc) from exc
