from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, TeacherUser
from app.modules.lessons.dashboard_service import teacher_dashboard
from app.modules.lessons.schemas import TeacherDashboardResponse

router = APIRouter(prefix="/api/v1/teacher", tags=["teacher-dashboard"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@router.get("/dashboard", response_model=TeacherDashboardResponse)
def dashboard(
    teacher: TeacherUser, db: DbSession, settings: AppSettings
) -> TeacherDashboardResponse:
    return teacher_dashboard(db, teacher.id, settings.app_timezone)
