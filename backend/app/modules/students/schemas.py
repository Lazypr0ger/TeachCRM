from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class StudentSummary(BaseModel):
    id: UUID
    user_id: UUID
    login: str
    status: str
    first_name: str
    last_name: str
    patronymic: str | None
    grade: int | None
    created_at: datetime


class StudentListResponse(BaseModel):
    items: list[StudentSummary]
    total: int
    page: int
    page_size: int


class StudentUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    patronymic: str | None = Field(default=None, max_length=100)
    grade: int | None = Field(default=None, ge=1, le=11)

    @field_validator("first_name", "last_name")
    @classmethod
    def required_name_is_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Имя и фамилия не могут быть пустыми")
        return value

    @model_validator(mode="after")
    def require_field(self) -> "StudentUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Укажите хотя бы одно поле")
        return self


class StudentDetail(StudentSummary):
    activated_at: datetime | None
    last_login_at: datetime | None
    updated_at: datetime


class OwnStudentProfile(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    patronymic: str | None
    grade: int | None
    updated_at: datetime


class OwnStudentProfileUpdate(StudentUpdateRequest):
    pass


class StudentAnonymizeRequest(BaseModel):
    confirmation: str = Field(min_length=3, max_length=120)
