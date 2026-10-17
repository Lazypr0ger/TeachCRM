from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Tutor CRM API"
    app_timezone: str = "Europe/Moscow"
    database_url: str = Field(
        default="postgresql+psycopg://tutorcrm:tutorcrm-dev-only@localhost:5432/tutorcrm"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

