from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class PublicSiteResponse(BaseModel):
    trials_enabled: bool


class TrialCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=300)
    grade: int = Field(ge=1, le=11)
    goal: str | None = Field(default=None, max_length=1000)
    preferred_start: datetime | None = None
    preferred_end: datetime | None = None
    comment: str | None = Field(default=None, max_length=2000)
    website: str | None = Field(default=None, max_length=100, exclude=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        parts = value.split()
        if not 2 <= len(parts) <= 3 or any(
            not part.replace("-", "").replace("'", "").isalpha() for part in parts
        ):
            raise ValueError("Укажите фамилию, имя и при наличии отчество")
        return " ".join(parts)

    @field_validator("goal", "comment")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @model_validator(mode="after")
    def validate_interval(self) -> "TrialCreateRequest":
        if (self.preferred_start is None) != (self.preferred_end is None):
            raise ValueError("Укажите начало и окончание желаемого интервала")
        if self.preferred_start is not None:
            if self.preferred_start.tzinfo is None or self.preferred_end is None:
                raise ValueError("Для времени нужен часовой пояс")
            if self.preferred_end.tzinfo is None or self.preferred_end <= self.preferred_start:
                raise ValueError("Окончание должно быть позже начала")
        return self


class TrialResponse(BaseModel):
    id: UUID
    name: str
    grade: int
    goal: str | None
    preferred_start: datetime | None
    preferred_end: datetime | None
    confirmed_start: datetime | None
    confirmed_end: datetime | None
    comment: str | None
    source: str
    status: str
    possible_existing_student: bool
    converted_student_id: UUID | None
    version: int
    created_at: datetime
    updated_at: datetime


class TrialPage(BaseModel):
    items: list[TrialResponse]
    total: int
    page: int
    page_size: int


class TrialUpdateRequest(BaseModel):
    status: str = Field(
        pattern="^(NEW|IN_REVIEW|RESCHEDULE_REQUESTED|CONFIRMED|COMPLETED|REJECTED|CANCELLED)$"
    )
    confirmed_start: datetime | None = None
    confirmed_end: datetime | None = None
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_confirmation(self) -> "TrialUpdateRequest":
        if self.status == "CONFIRMED":
            if self.confirmed_start is None or self.confirmed_end is None:
                raise ValueError("Для подтверждения укажите интервал")
            if self.confirmed_start.tzinfo is None or self.confirmed_end.tzinfo is None:
                raise ValueError("Для времени нужен часовой пояс")
            if self.confirmed_end <= self.confirmed_start:
                raise ValueError("Окончание должно быть позже начала")
        return self


class TrialConvertRequest(BaseModel):
    login: str | None = Field(
        default=None, min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$"
    )


class TrialConversionResponse(BaseModel):
    student_id: UUID
    login: str
    created: bool
    activation_url: str | None
    expires_at: str | None
