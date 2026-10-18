from datetime import date, datetime, time
from typing import Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.lessons.schemas import LessonResponse, aware


class AvailabilityRuleRequest(BaseModel):
    timezone: str = Field(default="Europe/Moscow", min_length=1, max_length=64)
    weekday: int = Field(ge=0, le=6)
    local_start_time: time
    local_end_time: time
    week_parity: Literal["ALL", "A", "B"] = "ALL"
    cycle_anchor_date: date
    effective_from: date
    effective_until: date | None = None
    is_available: bool = True

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Неизвестный часовой пояс") from exc
        return value

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.local_end_time <= self.local_start_time:
            raise ValueError("Окончание окна должно быть позже начала")
        if self.effective_until is not None and self.effective_until < self.effective_from:
            raise ValueError("Дата окончания должна быть не раньше даты начала")
        return self


class AvailabilityRuleResponse(AvailabilityRuleRequest):
    id: UUID
    created_at: datetime
    updated_at: datetime


class AvailabilityExceptionRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime
    kind: Literal["BLOCKED", "AVAILABLE_OVERRIDE"]
    private_reason: str | None = Field(default=None, max_length=2_000)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime) -> datetime:
        if not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Окончание интервала должно быть позже начала")
        return self


class AvailabilityExceptionResponse(AvailabilityExceptionRequest):
    id: UUID
    created_at: datetime
    updated_at: datetime


class StudentAvailabilityRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime
    state: Literal["AVAILABLE", "BUSY"]

    @field_validator("starts_at", "ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime) -> datetime:
        if not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @model_validator(mode="after")
    def valid_range(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Окончание интервала должно быть позже начала")
        return self


class StudentAvailabilityResponse(StudentAvailabilityRequest):
    id: UUID
    conflicts_with_lesson: bool
    created_at: datetime
    updated_at: datetime


class StudentScheduleResponse(BaseModel):
    lessons: list[LessonResponse]
    availability: list[StudentAvailabilityResponse]
