from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, UUIDPrimaryKeyMixin


class FilePurpose:
    LESSON_MATERIAL = "LESSON_MATERIAL"
    ASSIGNMENT_MATERIAL = "ASSIGNMENT_MATERIAL"
    HOMEWORK = "HOMEWORK"


class UploadStatus:
    INITIATED = "INITIATED"
    UPLOADED = "UPLOADED"
    COMPLETED = "COMPLETED"


class FileUploadTicket(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "file_upload_tickets"
    __table_args__ = (
        CheckConstraint(
            "purpose IN ('LESSON_MATERIAL', 'ASSIGNMENT_MATERIAL', 'HOMEWORK')",
            name="ck_file_ticket_purpose",
        ),
        CheckConstraint(
            "status IN ('INITIATED', 'UPLOADED', 'COMPLETED')",
            name="ck_file_ticket_status",
        ),
        Index("ix_file_ticket_owner_status", "owner_user_id", "status"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[UUID] = mapped_column(nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    declared_byte_size: Mapped[int] = mapped_column(nullable=False)
    detected_mime_type: Mapped[str | None] = mapped_column(String(120))
    actual_byte_size: Mapped[int | None]
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_file_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StoredFile(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint("byte_size > 0", name="ck_files_positive_size"),
        CheckConstraint(
            "purpose IN ('LESSON_MATERIAL', 'ASSIGNMENT_MATERIAL', 'HOMEWORK')",
            name="ck_files_purpose",
        ),
    )

    owner_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    byte_size: Mapped[int] = mapped_column(nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FileLink(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "file_links"
    __table_args__ = (
        UniqueConstraint("file_id", "entity_type", "entity_id", name="uq_file_link_target"),
        Index("ix_file_links_target", "entity_type", "entity_id"),
    )

    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(nullable=False)
