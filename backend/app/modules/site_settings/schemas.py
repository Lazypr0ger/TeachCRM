from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicSiteResponse(BaseModel):
    brand_name: str
    tagline: str | None
    about_text: str | None
    directions: list[str]
    advantages: list[str]
    confirmed_results: list[str]
    pricing_text: str | None
    privacy_text: str | None
    trials_enabled: bool
    timezone: str


class TeacherSiteSettingsResponse(PublicSiteResponse):
    configured_trials_enabled: bool
    trial_feature_available: bool
    version: int
    updated_at: datetime | None


class SiteSettingsUpdate(BaseModel):
    brand_name: str | None = Field(default=None, min_length=1, max_length=120)
    tagline: str | None = Field(default=None, max_length=300)
    about_text: str | None = Field(default=None, max_length=5000)
    directions: list[str] | None = Field(default=None, max_length=12)
    advantages: list[str] | None = Field(default=None, max_length=12)
    confirmed_results: list[str] | None = Field(default=None, max_length=12)
    pricing_text: str | None = Field(default=None, max_length=3000)
    privacy_text: str | None = Field(default=None, max_length=10000)
    trials_enabled: bool | None = None
    version: int = Field(ge=0)

    @field_validator("brand_name")
    @classmethod
    def clean_brand(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Название не может быть пустым")
        return value

    @field_validator("tagline", "about_text", "pricing_text", "privacy_text")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("directions", "advantages", "confirmed_results")
    @classmethod
    def clean_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 300 for item in cleaned):
            raise ValueError("Один пункт не может быть длиннее 300 символов")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Пункты не должны повторяться")
        return cleaned

    @model_validator(mode="after")
    def require_change(self) -> "SiteSettingsUpdate":
        if self.model_fields_set == {"version"}:
            raise ValueError("Укажите хотя бы одно изменяемое поле")
        return self
