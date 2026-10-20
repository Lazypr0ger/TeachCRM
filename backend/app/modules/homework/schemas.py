from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.files.schemas import FileResponse
from app.modules.lessons.schemas import aware


class AssignmentCreateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=20_000)
    due_at: datetime | None = None

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Задание не может быть пустым")
        return value.strip()

    @field_validator("due_at")
    @classmethod
    def due_at_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and not aware(value):
            raise ValueError("Срок сдачи должен содержать часовой пояс")
        return value


class AssignmentUpdateRequest(BaseModel):
    version: int = Field(ge=1)
    description: str | None = Field(default=None, min_length=1, max_length=20_000)
    due_at: datetime | None = None

    @field_validator("description")
    @classmethod
    def description_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Задание не может быть пустым")
        return value.strip() if value is not None else None

    @field_validator("due_at")
    @classmethod
    def due_at_has_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and not aware(value):
            raise ValueError("Срок сдачи должен содержать часовой пояс")
        return value

    @model_validator(mode="after")
    def has_changes(self) -> Self:
        if self.model_fields_set == {"version"}:
            raise ValueError("Укажите хотя бы одно изменение")
        return self


class SubmissionCreateRequest(BaseModel):
    answer_text: str | None = Field(default=None, max_length=20_000)
    file_ids: list[UUID] = Field(default_factory=list, max_length=10)
    idempotency_key: str = Field(min_length=8, max_length=100)

    @field_validator("answer_text")
    @classmethod
    def normalize_answer(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def has_content(self) -> Self:
        if self.answer_text is None and not self.file_ids:
            raise ValueError("Добавьте текст ответа или хотя бы один файл")
        if len(set(self.file_ids)) != len(self.file_ids):
            raise ValueError("Один файл указан несколько раз")
        return self


class AssignmentResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    description: str
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    files: list[FileResponse]


class SubmissionResponse(BaseModel):
    id: UUID
    assignment_id: UUID
    answer_text: str | None
    submitted_at: datetime
    files: list[FileResponse]


class HomeworkResponse(BaseModel):
    state: str
    assignment: AssignmentResponse | None
    submission: SubmissionResponse | None
    draft_files: list[FileResponse] = Field(default_factory=list)


class StudentHomeworkSummary(BaseModel):
    lesson_id: UUID
    lesson_title: str
    lesson_starts_at: datetime
    state: str
    assignment_description: str | None
    due_at: datetime | None
    submitted_at: datetime | None
