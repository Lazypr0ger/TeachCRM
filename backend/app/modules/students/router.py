from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.students.schemas import StudentDetail, StudentListResponse, StudentUpdateRequest
from app.modules.students.service import (
    StudentNotFoundError,
    get_student,
    list_students,
    student_detail,
    update_student,
)

router = APIRouter(prefix="/api/v1/teacher/students", tags=["teacher-students"])


@router.get("", response_model=StudentListResponse)
def students(
    _teacher: TeacherUser,
    db: DbSession,
    search: Annotated[str | None, Query(max_length=100)] = None,
    grade: Annotated[int | None, Query(ge=1, le=11)] = None,
    student_status: Literal["INVITED", "ACTIVE", "SUSPENDED"] | None = None,
    sort: Literal["name", "created_desc", "created_asc"] = "name",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentListResponse:
    items, total = list_students(
        db,
        search=search,
        grade=grade,
        student_status=student_status,
        sort=sort,
        page=page,
        page_size=page_size,
    )
    return StudentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{student_id}", response_model=StudentDetail)
def student(student_id: UUID, _teacher: TeacherUser, db: DbSession) -> StudentDetail:
    try:
        profile, user = get_student(db, student_id)
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден"
        ) from exc
    return student_detail(profile, user)


@router.patch("/{student_id}", response_model=StudentDetail)
def edit_student(
    student_id: UUID,
    payload: StudentUpdateRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
) -> StudentDetail:
    try:
        return update_student(db, student_id, payload, teacher)
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден"
        ) from exc
