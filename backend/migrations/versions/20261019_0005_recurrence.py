"""Add weekly lesson recurrence and protected occurrence exceptions."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0005"
down_revision = "20261019_0004"
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
        "lesson_recurrence_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "teacher_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("join_url", sa.String(2048)),
        sa.Column("local_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("by_weekday", sa.Integer(), nullable=False),
        sa.Column("interval_weeks", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date()),
        sa.Column("count_limit", sa.Integer()),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        *timestamps(),
        sa.CheckConstraint("duration_minutes BETWEEN 5 AND 480", name="ck_recurrence_duration"),
        sa.CheckConstraint("interval_weeks IN (1, 2)", name="ck_recurrence_interval"),
        sa.CheckConstraint("by_weekday BETWEEN 0 AND 6", name="ck_recurrence_weekday"),
        sa.CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="ck_recurrence_dates"),
        sa.CheckConstraint("count_limit IS NULL OR count_limit > 0", name="ck_recurrence_count"),
    )
    op.create_index(
        "ix_recurrence_teacher_active",
        "lesson_recurrence_rules",
        ["teacher_id", "active"],
    )
    op.add_column(
        "lessons",
        sa.Column(
            "recurrence_rule_id",
            sa.Uuid(),
            sa.ForeignKey("lesson_recurrence_rules.id", ondelete="SET NULL"),
        ),
    )
    op.add_column("lessons", sa.Column("recurrence_instance_key", sa.String(32)))
    op.create_unique_constraint(
        "uq_lessons_recurrence_instance",
        "lessons",
        ["recurrence_rule_id", "recurrence_instance_key"],
    )
    op.create_table(
        "recurrence_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "rule_id",
            sa.Uuid(),
            sa.ForeignKey("lesson_recurrence_rules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurrence_key", sa.String(32), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column(
            "replacement_lesson_id",
            sa.Uuid(),
            sa.ForeignKey("lessons.id", ondelete="SET NULL"),
        ),
        *timestamps(),
        sa.UniqueConstraint("rule_id", "occurrence_key", name="uq_recurrence_exception_key"),
        sa.CheckConstraint(
            "action IN ('MODIFIED', 'CANCELLED')", name="ck_recurrence_exception_action"
        ),
    )


def downgrade() -> None:
    op.drop_table("recurrence_exceptions")
    op.drop_constraint("uq_lessons_recurrence_instance", "lessons", type_="unique")
    op.drop_column("lessons", "recurrence_instance_key")
    op.drop_column("lessons", "recurrence_rule_id")
    op.drop_table("lesson_recurrence_rules")
