from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime

from app.modules.auth.dependencies import DbSession, StudentUser
from app.modules.lessons.schemas import LessonListResponse, LessonResponse, StudentDashboardResponse
from app.modules.lessons.service import (
    LessonNotFoundError,
    get_lesson_row,
    lesson_response,
    list_lessons,
    next_student_lesson,
    student_profile_for_user,
)

router = APIRouter(prefix="/api/v1/student", tags=["student-lessons"])


@router.get("/lessons", response_model=LessonListResponse)
def lessons(
    student: StudentUser,
    db: DbSession,
    lesson_status: Literal["SCHEDULED", "COMPLETED", "CANCELLED"] | None = None,
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> LessonListResponse:
    profile = student_profile_for_user(db, student.id)
    items, total = list_lessons(
        db,
        student_id=profile.id,
        lesson_status=lesson_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return LessonListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/lessons/{lesson_id}", response_model=LessonResponse)
def lesson(lesson_id: UUID, student: StudentUser, db: DbSession) -> LessonResponse:
    profile = student_profile_for_user(db, student.id)
    try:
        record, record_profile = get_lesson_row(db, lesson_id, profile.id)
    except LessonNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Урок не найден") from exc
    return lesson_response(record, record_profile)


@router.get("/dashboard", response_model=StudentDashboardResponse)
def dashboard(student: StudentUser, db: DbSession) -> StudentDashboardResponse:
    profile = student_profile_for_user(db, student.id)
    return StudentDashboardResponse(next_lesson=next_student_lesson(db, profile.id))
