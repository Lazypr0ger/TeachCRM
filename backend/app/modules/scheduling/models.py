from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeekParity:
    ALL = "ALL"
    A = "A"
    B = "B"


class AvailabilityExceptionKind:
    BLOCKED = "BLOCKED"
    AVAILABLE_OVERRIDE = "AVAILABLE_OVERRIDE"


class StudentAvailabilityState:
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"


class AvailabilityRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "availability_rules"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_rules_weekday"),
        CheckConstraint("local_end_time > local_start_time", name="ck_availability_rules_time"),
        CheckConstraint("week_parity IN ('ALL', 'A', 'B')", name="ck_availability_rules_parity"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_availability_rules_dates",
        ),
        Index("ix_availability_rules_teacher_weekday", "teacher_id", "weekday"),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    weekday: Mapped[int] = mapped_column(nullable=False)
    local_start_time: Mapped[time] = mapped_column(Time(), nullable=False)
    local_end_time: Mapped[time] = mapped_column(Time(), nullable=False)
    week_parity: Mapped[str] = mapped_column(String(3), nullable=False)
    cycle_anchor_date: Mapped[date] = mapped_column(Date(), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date(), nullable=False)
    effective_until: Mapped[date | None] = mapped_column(Date())
    is_available: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)


class AvailabilityException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "availability_exceptions"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_availability_exceptions_interval"),
        CheckConstraint(
            "kind IN ('BLOCKED', 'AVAILABLE_OVERRIDE')",
            name="ck_availability_exceptions_kind",
        ),
        Index("ix_availability_exceptions_teacher_starts", "teacher_id", "starts_at"),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    private_reason: Mapped[str | None] = mapped_column(Text())


class StudentAvailability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "student_availability"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_student_availability_interval"),
        CheckConstraint("state IN ('AVAILABLE', 'BUSY')", name="ck_student_availability_state"),
        Index("ix_student_availability_student_starts", "student_id", "starts_at"),
    )

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)


class RecurrenceExceptionAction:
    MODIFIED = "MODIFIED"
    CANCELLED = "CANCELLED"


class LessonRecurrenceRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_recurrence_rules"
    __table_args__ = (
        CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_recurrence_duration"),
        CheckConstraint("interval_weeks IN (1, 2)", name="ck_recurrence_interval"),
        CheckConstraint("by_weekday BETWEEN 0 AND 6", name="ck_recurrence_weekday"),
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_recurrence_dates"),
        CheckConstraint("count_limit IS NULL OR count_limit > 0", name="ck_recurrence_count"),
        Index("ix_recurrence_teacher_active", "teacher_id", "active"),
    )

    teacher_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text())
    join_url: Mapped[str | None] = mapped_column(String(2048))
    local_time: Mapped[time] = mapped_column(Time(), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    by_weekday: Mapped[int] = mapped_column(nullable=False)
    interval_weeks: Mapped[int] = mapped_column(nullable=False)
    starts_on: Mapped[date] = mapped_column(Date(), nullable=False)
    ends_on: Mapped[date | None] = mapped_column(Date())
    count_limit: Mapped[int | None]
    active: Mapped[bool] = mapped_column(Boolean(), default=True, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)


class RecurrenceException(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recurrence_exceptions"
    __table_args__ = (
        UniqueConstraint("rule_id", "occurrence_key", name="uq_recurrence_exception_key"),
        CheckConstraint(
            "action IN ('MODIFIED', 'CANCELLED')", name="ck_recurrence_exception_action"
        ),
    )

    rule_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_recurrence_rules.id", ondelete="CASCADE"), nullable=False
    )
    occurrence_key: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    replacement_lesson_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL")
    )
