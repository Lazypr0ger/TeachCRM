from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Tutor CRM API"
    app_timezone: str = "Europe/Moscow"
    app_base_url: str = "http://localhost:3000"
    session_cookie_name: str = "tutorcrm_session"
    session_absolute_hours: int = 168
    session_idle_hours: int = 12
    invitation_ttl_hours: int = 48
    password_reset_ttl_minutes: int = 60
    s3_endpoint: str = "http://localhost:4566"
    s3_bucket: str = "tutorcrm-private"
    s3_access_key: str = "test"
    s3_secret_key: str = "test"
    s3_region: str = "eu-central-1"
    file_max_bytes: int = 15 * 1024 * 1024
    file_max_per_target: int = 10
    upload_ticket_ttl_minutes: int = 30
    trial_booking_enabled: bool = False
    database_url: str = Field(
        default="postgresql+psycopg://tutorcrm:tutorcrm-dev-only@localhost:5432/tutorcrm"
    )

    @property
    def secure_cookies(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
