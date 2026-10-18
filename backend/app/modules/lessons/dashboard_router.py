from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, TeacherUser
from app.modules.lessons.schemas import TeacherDashboardResponse
from app.modules.lessons.service import today_teacher_lessons

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-dashboard"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/dashboard", response_model=TeacherDashboardResponse)
def dashboard(
    teacher: TeacherUser, db: DbSession, settings: AppSettings
) -> TeacherDashboardResponse:
    return TeacherDashboardResponse(
        today_lessons=today_teacher_lessons(db, teacher.id, settings.app_timezone)
    )
