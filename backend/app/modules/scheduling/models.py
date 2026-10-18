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
