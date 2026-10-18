from datetime import date, datetime, time
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


def https_url(value: str | None) -> bool:
    if value is None or value == "":
        return True
    parsed = urlsplit(value)
    return parsed.scheme == "https" and parsed.hostname is not None


class RecurrenceRuleCreateRequest(BaseModel):
    student_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    join_url: str | None = Field(default=None, max_length=2048)
    local_time: time
    duration_minutes: int = Field(ge=5, le=480)
    timezone: str = Field(default="Europe/Moscow", min_length=1, max_length=64)
    by_weekday: int = Field(ge=0, le=6)
    interval_weeks: int = Field(ge=1, le=2)
    starts_on: date
    ends_on: date | None = None
    count_limit: int | None = Field(default=None, ge=1, le=520)

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Название не может быть пустым")
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Неизвестный часовой пояс") from exc
        return value

    @field_validator("join_url")
    @classmethod
    def join_url_is_https(cls, value: str | None) -> str | None:
        if not https_url(value):
            raise ValueError("Ссылка подключения должна использовать HTTPS")
        return value

    @model_validator(mode="after")
    def dates_are_valid(self) -> Self:
        if self.starts_on.weekday() != self.by_weekday:
            raise ValueError("Дата начала должна совпадать с выбранным днём недели")
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("Дата окончания должна быть не раньше даты начала")
        if self.ends_on is not None and self.count_limit is not None:
            raise ValueError("Укажите дату окончания или число занятий")
        return self


class RecurrenceRuleUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    join_url: str | None = Field(default=None, max_length=2048)

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Название не может быть пустым")
        return value.strip() if value else value

    @field_validator("join_url")
    @classmethod
    def join_url_is_https(cls, value: str | None) -> str | None:
        if not https_url(value):
            raise ValueError("Ссылка подключения должна использовать HTTPS")
        return value

    @model_validator(mode="after")
    def has_changes(self) -> Self:
        if self.model_fields_set == {"version"}:
            raise ValueError("Укажите хотя бы одно изменение")
        return self


class RecurrenceRuleResponse(BaseModel):
    id: UUID
    teacher_id: UUID
    student_id: UUID
    student_name: str
    title: str
    description: str | None
    join_url: str | None
    local_time: time
    duration_minutes: int
    timezone: str
    by_weekday: int
    interval_weeks: int
    starts_on: date
    ends_on: date | None
    count_limit: int | None
    active: bool
    version: int
    materialized_count: int = 0
    created_at: datetime
    updated_at: datetime
