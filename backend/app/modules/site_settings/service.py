from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.modules.auth.models import User
from app.modules.auth.service import add_audit
from app.modules.site_settings.models import SiteSettings
from app.modules.site_settings.schemas import (
    PublicSiteResponse,
    SiteSettingsUpdate,
    TeacherSiteSettingsResponse,
)

DEFAULT_DIRECTIONS = ["Индивидуальные занятия", "Подготовка к контрольным", "Разбор тем"]
DEFAULT_ADVANTAGES = ["Прозрачное расписание", "Домашние задания в одном месте"]


class SiteSettingsConflictError(Exception):
    pass


def get_site_settings(db: Session) -> SiteSettings | None:
    return db.scalar(select(SiteSettings).where(SiteSettings.singleton_key == 1))


def public_site(db: Session, settings: Settings) -> PublicSiteResponse:
    item = get_site_settings(db)
    configured = item.trials_enabled if item else True
    return PublicSiteResponse(
        brand_name=item.brand_name if item else "Tutor CRM",
        tagline=item.tagline if item else "Учёба, расписание и расчёты в одном кабинете",
        about_text=item.about_text if item else None,
        directions=item.directions if item else DEFAULT_DIRECTIONS,
        advantages=item.advantages if item else DEFAULT_ADVANTAGES,
        confirmed_results=item.confirmed_results if item else [],
        pricing_text=item.pricing_text if item else None,
        privacy_text=item.privacy_text if item else None,
        trials_enabled=settings.trial_booking_enabled and configured,
        timezone=settings.app_timezone,
    )


def teacher_site(db: Session, settings: Settings) -> TeacherSiteSettingsResponse:
    public = public_site(db, settings)
    item = get_site_settings(db)
    return TeacherSiteSettingsResponse(
        **public.model_dump(),
        configured_trials_enabled=item.trials_enabled if item else True,
        trial_feature_available=settings.trial_booking_enabled,
        version=item.version if item else 0,
        updated_at=item.updated_at if item else None,
    )


def update_site(
    db: Session,
    payload: SiteSettingsUpdate,
    teacher: User,
    settings: Settings,
) -> TeacherSiteSettingsResponse:
    item = db.scalar(select(SiteSettings).where(SiteSettings.singleton_key == 1).with_for_update())
    if item is None:
        if payload.version != 0:
            raise SiteSettingsConflictError("Настройки уже изменились, обновите страницу")
        item = SiteSettings(singleton_key=1, updated_by_user_id=teacher.id)
        db.add(item)
        db.flush()
    elif item.version != payload.version:
        raise SiteSettingsConflictError("Настройки уже изменились, обновите страницу")

    for field, value in payload.model_dump(exclude={"version"}, exclude_unset=True).items():
        setattr(item, field, value)
    item.updated_by_user_id = teacher.id
    if payload.version > 0:
        item.version += 1
    add_audit(db, teacher.id, "SITE_SETTINGS_UPDATED", "site_settings", item.id)
    db.commit()
    db.refresh(item)
    return teacher_site(db, settings)


def trials_are_enabled(db: Session, settings: Settings) -> bool:
    item = get_site_settings(db)
    return settings.trial_booking_enabled and (item is None or item.trials_enabled)
