"""Create individual lessons with database overlap protection."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0003"
down_revision = "20261017_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "teacher_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
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
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("join_url", sa.String(2048)),
        sa.Column("status", sa.String(16), server_default="SCHEDULED", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("ends_at > starts_at", name="ck_lessons_valid_interval"),
        sa.CheckConstraint(
            "status IN ('SCHEDULED', 'COMPLETED', 'CANCELLED')", name="ck_lessons_status"
        ),
    )
    op.create_index("ix_lessons_teacher_starts", "lessons", ["teacher_id", "starts_at"])
    op.create_index("ix_lessons_student_starts", "lessons", ["student_id", "starts_at"])
    op.execute(
        """
        ALTER TABLE lessons ADD CONSTRAINT excl_lessons_teacher_overlap
        EXCLUDE USING gist (
            teacher_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status = 'SCHEDULED')
        """
    )
    op.execute(
        """
        ALTER TABLE lessons ADD CONSTRAINT excl_lessons_student_overlap
        EXCLUDE USING gist (
            student_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (status = 'SCHEDULED')
        """
    )


def downgrade() -> None:
    op.drop_table("lessons")
