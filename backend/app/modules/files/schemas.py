from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    purpose: Literal["LESSON_MATERIAL", "ASSIGNMENT_MATERIAL", "HOMEWORK"]
    target_type: Literal["LESSON", "ASSIGNMENT", "SUBMISSION"]
    target_id: UUID
    original_filename: str = Field(min_length=1, max_length=255)
    byte_size: int = Field(gt=0)


class UploadTicketResponse(BaseModel):
    ticket_id: UUID
    upload_url: str
    expires_at: datetime
    max_bytes: int


class FileResponse(BaseModel):
    id: UUID
    original_filename: str
    mime_type: str
    byte_size: int
    purpose: str
    checksum_sha256: str
    created_at: datetime
    download_url: str
