from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.modules.auth.dependencies import DbSession, TeacherCsrfUser, TeacherUser
from app.modules.site_settings.schemas import (
    PublicSiteResponse,
    SiteSettingsUpdate,
    TeacherSiteSettingsResponse,
)
from app.modules.site_settings.service import (
    SiteSettingsConflictError,
    public_site,
    teacher_site,
    update_site,
)

public_router = APIRouter(prefix="/api/v1/public", tags=["public"])
teacher_router = APIRouter(prefix="/api/v1/teacher/settings/site", tags=["teacher-settings"])
AppSettings = Annotated[Settings, Depends(get_settings)]


@public_router.get("/site", response_model=PublicSiteResponse)
def get_public_site(db: DbSession, settings: AppSettings) -> PublicSiteResponse:
    return public_site(db, settings)


@teacher_router.get("", response_model=TeacherSiteSettingsResponse)
def get_teacher_site(
    _teacher: TeacherUser, db: DbSession, settings: AppSettings
) -> TeacherSiteSettingsResponse:
    return teacher_site(db, settings)


@teacher_router.patch("", response_model=TeacherSiteSettingsResponse)
def patch_teacher_site(
    payload: SiteSettingsUpdate,
    teacher: TeacherCsrfUser,
    db: DbSession,
    settings: AppSettings,
) -> TeacherSiteSettingsResponse:
    try:
        return update_site(db, payload, teacher, settings)
    except SiteSettingsConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
