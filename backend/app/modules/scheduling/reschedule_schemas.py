from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.lessons.schemas import aware


class RescheduleCreateRequest(BaseModel):
    proposed_starts_at: datetime
    proposed_ends_at: datetime
    reason: str | None = Field(default=None, max_length=2_000)

    @field_validator("proposed_starts_at", "proposed_ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime) -> datetime:
        if not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @model_validator(mode="after")
    def interval_is_valid(self) -> Self:
        if self.proposed_ends_at <= self.proposed_starts_at:
            raise ValueError("Окончание должно быть позже начала")
        return self


class RescheduleCounterRequest(BaseModel):
    counter_starts_at: datetime
    counter_ends_at: datetime
    response_note: str | None = Field(default=None, max_length=2_000)

    @field_validator("counter_starts_at", "counter_ends_at")
    @classmethod
    def datetime_has_timezone(cls, value: datetime) -> datetime:
        if not aware(value):
            raise ValueError("Дата и время должны содержать часовой пояс")
        return value

    @model_validator(mode="after")
    def interval_is_valid(self) -> Self:
        if self.counter_ends_at <= self.counter_starts_at:
            raise ValueError("Окончание должно быть позже начала")
        return self


class RescheduleDecisionRequest(BaseModel):
    response_note: str | None = Field(default=None, max_length=2_000)


class RescheduleResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    student_id: UUID
    student_name: str
    lesson_title: str
    original_starts_at: datetime
    original_ends_at: datetime
    proposed_starts_at: datetime
    proposed_ends_at: datetime
    reason: str | None
    status: Literal["PENDING", "COUNTER_OFFER", "ACCEPTED", "REJECTED", "CANCELLED"]
    counter_starts_at: datetime | None
    counter_ends_at: datetime | None
    response_note: str | None
    responded_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
