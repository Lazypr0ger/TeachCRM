from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TrialStatus:
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    RESCHEDULE_REQUESTED = "RESCHEDULE_REQUESTED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class TrialRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trial_requests"
    __table_args__ = (
        CheckConstraint("grade BETWEEN 1 AND 11", name="ck_trial_grade"),
        CheckConstraint("source IN ('WEB', 'TELEGRAM')", name="ck_trial_source"),
        CheckConstraint(
            "status IN ('NEW', 'IN_REVIEW', 'RESCHEDULE_REQUESTED', 'CONFIRMED', "
            "'COMPLETED', 'REJECTED', 'CANCELLED')",
            name="ck_trial_status",
        ),
        CheckConstraint(
            "(preferred_start IS NULL AND preferred_end IS NULL) OR "
            "(preferred_start IS NOT NULL AND preferred_end > preferred_start)",
            name="ck_trial_preferred_interval",
        ),
        CheckConstraint(
            "(confirmed_start IS NULL AND confirmed_end IS NULL) OR "
            "(confirmed_start IS NOT NULL AND confirmed_end > confirmed_start)",
            name="ck_trial_confirmed_interval",
        ),
        CheckConstraint(
            "status NOT IN ('CONFIRMED', 'COMPLETED') OR "
            "(teacher_id IS NOT NULL AND confirmed_start IS NOT NULL "
            "AND confirmed_end IS NOT NULL)",
            name="ck_trial_confirmed_has_slot",
        ),
        Index("ix_trial_status_created", "status", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False)
    grade: Mapped[int] = mapped_column(nullable=False)
    goal: Mapped[str | None] = mapped_column(Text())
    contact_method: Mapped[str | None] = mapped_column(String(30))
    contact_normalized: Mapped[str | None] = mapped_column(String(300))
    preferred_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    preferred_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text())
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    possible_existing_student: Mapped[bool] = mapped_column(
        Boolean(), default=False, nullable=False
    )
    teacher_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    converted_student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="RESTRICT"), unique=True
    )
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class TrialSubmissionAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "trial_submission_attempts"
    __table_args__ = (Index("ix_trial_attempt_hash_time", "client_hash", "created_at"),)

    client_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
