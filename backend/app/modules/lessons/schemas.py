from datetime import datetime
from typing import Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


def aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def valid_https_url(value: str | None) -> bool:
    if value is None or value == "":
        return True
    parsed = urlsplit(value)
    return parsed.scheme == "https" and parsed.hostname is not None


class LessonCreateRequest(BaseModel):
    student_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    starts_at: datetime
    ends_at: datetime
    join_url: str | None = Field(default=None, max_length=2048)

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Название не может быть пустым")
        return value.strip()

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime) -> datetime:
        if not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @field_validator("join_url")
    @classmethod
    def join_url_is_https(cls, value: str | None) -> str | None:
        if not valid_https_url(value):
            raise ValueError("Ссылка подключения должна использовать HTTPS")
        return value

    @model_validator(mode="after")
    def interval_is_valid(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Окончание урока должно быть позже начала")
        return self


class LessonUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    join_url: str | None = Field(default=None, max_length=2048)

    @field_validator("title")
    @classmethod
    def title_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Название не может быть пустым")
        return value.strip() if value is not None else None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @field_validator("join_url")
    @classmethod
    def join_url_is_https(cls, value: str | None) -> str | None:
        if not valid_https_url(value):
            raise ValueError("Ссылка подключения должна использовать HTTPS")
        return value

    @model_validator(mode="after")
    def has_changes(self) -> Self:
        if self.model_fields_set == {"version"}:
            raise ValueError("Укажите хотя бы одно изменение")
        return self


class LessonResponse(BaseModel):
    id: UUID
    teacher_id: UUID
    student_id: UUID
    student_name: str
    title: str
    description: str | None
    starts_at: datetime
    ends_at: datetime
    join_url: str | None
    status: str
    completed_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime


class LessonListResponse(BaseModel):
    items: list[LessonResponse]
    total: int
    page: int
    page_size: int


class StudentDashboardResponse(BaseModel):
    next_lesson: LessonResponse | None


class TeacherDashboardResponse(BaseModel):
    today_lessons: list[LessonResponse]
