from uuid import UUID

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SiteSettings(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "site_settings"
    __table_args__ = (CheckConstraint("singleton_key = 1", name="ck_site_settings_singleton"),)

    singleton_key: Mapped[int] = mapped_column(unique=True, default=1, nullable=False)
    brand_name: Mapped[str] = mapped_column(String(120), default="Tutor CRM", nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(300))
    about_text: Mapped[str | None] = mapped_column(Text())
    directions: Mapped[list[str]] = mapped_column(JSON(), default=list, nullable=False)
    advantages: Mapped[list[str]] = mapped_column(JSON(), default=list, nullable=False)
    confirmed_results: Mapped[list[str]] = mapped_column(JSON(), default=list, nullable=False)
    pricing_text: Mapped[str | None] = mapped_column(Text())
    privacy_text: Mapped[str | None] = mapped_column(Text())
    trials_enabled: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow", nullable=False)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)
