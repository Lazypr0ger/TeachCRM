from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.auth.schemas import MessageResponse
from app.modules.files.storage import ObjectStorage, get_storage
from app.modules.students.schemas import (
    StudentAnonymizeRequest,
    StudentDetail,
    StudentListResponse,
    StudentUpdateRequest,
)
from app.modules.students.service import (
    StudentAnonymizeError,
    StudentNotFoundError,
    anonymize_student,
    export_student_data,
    get_student,
    list_students,
    student_detail,
    update_student,
)

router = APIRouter(prefix="/api/v1/teacher/students", tags=["teacher-students"])
Storage = Annotated[ObjectStorage, Depends(get_storage)]


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


@router.get("/{student_id}/export")
def export_student(student_id: UUID, teacher: TeacherUser, db: DbSession) -> JSONResponse:
    try:
        data = export_student_data(db, student_id, teacher)
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден"
        ) from exc
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={
            "Content-Disposition": f'attachment; filename="student-{student_id}.json"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{student_id}/anonymize", response_model=MessageResponse)
def anonymize(
    student_id: UUID,
    payload: StudentAnonymizeRequest,
    teacher: TeacherCsrfUser,
    db: DbSession,
    storage: Storage,
) -> MessageResponse:
    try:
        anonymize_student(db, student_id, payload.confirmation, teacher, storage)
    except StudentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ученик не найден"
        ) from exc
    except StudentAnonymizeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return MessageResponse(message="Данные ученика анонимизированы")
