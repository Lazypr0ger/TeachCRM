from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class PasswordTokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=12, max_length=128)


class PasswordResetRequest(BaseModel):
    login: str = Field(min_length=3, max_length=120)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    login: str
    status: str


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class MessageResponse(BaseModel):
    message: str


class StudentCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    patronymic: str | None = Field(default=None, max_length=100)
    grade: int | None = Field(default=None, ge=1, le=11)
    login: str | None = Field(
        default=None, min_length=3, max_length=120, pattern=r"^[a-zA-Z0-9_.-]+$"
    )


class InvitationResponse(BaseModel):
    student_id: UUID
    user_id: UUID
    login: str
    activation_token: str
    activation_url: str
    expires_at: str


class ResetLinkResponse(BaseModel):
    reset_token: str
    reset_url: str
    expires_at: str


class ResetRequestResponse(BaseModel):
    id: UUID
    user_id: UUID
    login: str
    role: str
    requested_at: str
