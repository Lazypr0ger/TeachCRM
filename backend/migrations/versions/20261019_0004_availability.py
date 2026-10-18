"""Add teacher and student availability."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0004"
down_revision = "20261019_0003"
branch_labels = None
depends_on = None


def timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "availability_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "teacher_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("local_start_time", sa.Time(), nullable=False),
        sa.Column("local_end_time", sa.Time(), nullable=False),
        sa.Column("week_parity", sa.String(3), nullable=False),
        sa.Column("cycle_anchor_date", sa.Date(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamps(),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_availability_rules_weekday"),
        sa.CheckConstraint("local_end_time > local_start_time", name="ck_availability_rules_time"),
        sa.CheckConstraint("week_parity IN ('ALL', 'A', 'B')", name="ck_availability_rules_parity"),
        sa.CheckConstraint(
            "effective_until IS NULL OR effective_until >= effective_from",
            name="ck_availability_rules_dates",
        ),
    )
    op.create_index(
        "ix_availability_rules_teacher_weekday",
        "availability_rules",
        ["teacher_id", "weekday"],
    )

    op.create_table(
        "availability_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "teacher_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("private_reason", sa.Text()),
        *timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name="ck_availability_exceptions_interval"),
        sa.CheckConstraint(
            "kind IN ('BLOCKED', 'AVAILABLE_OVERRIDE')", name="ck_availability_exceptions_kind"
        ),
    )
    op.create_index(
        "ix_availability_exceptions_teacher_starts",
        "availability_exceptions",
        ["teacher_id", "starts_at"],
    )
    op.execute(
        """
        ALTER TABLE availability_exceptions
        ADD CONSTRAINT excl_availability_exceptions_overlap
        EXCLUDE USING gist (
            teacher_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        """
    )

    op.create_table(
        "student_availability",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        *timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name="ck_student_availability_interval"),
        sa.CheckConstraint("state IN ('AVAILABLE', 'BUSY')", name="ck_student_availability_state"),
    )
    op.create_index(
        "ix_student_availability_student_starts",
        "student_availability",
        ["student_id", "starts_at"],
    )
    op.execute(
        """
        ALTER TABLE student_availability
        ADD CONSTRAINT excl_student_availability_overlap
        EXCLUDE USING gist (
            student_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        )
        """
    )


def downgrade() -> None:
    op.drop_table("student_availability")
    op.drop_table("availability_exceptions")
    op.drop_table("availability_rules")
