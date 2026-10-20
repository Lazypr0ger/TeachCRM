"""Add guarded trial request intake and teacher workflow."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0015"
down_revision = "20261019_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trial_submission_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_trial_attempt_hash_time",
        "trial_submission_attempts",
        ["client_hash", "created_at"],
    )
    op.create_table(
        "trial_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("grade", sa.Integer(), nullable=False),
        sa.Column("goal", sa.Text()),
        sa.Column("contact_method", sa.String(30)),
        sa.Column("contact_normalized", sa.String(300)),
        sa.Column("preferred_start", sa.DateTime(timezone=True)),
        sa.Column("preferred_end", sa.DateTime(timezone=True)),
        sa.Column("confirmed_start", sa.DateTime(timezone=True)),
        sa.Column("confirmed_end", sa.DateTime(timezone=True)),
        sa.Column("comment", sa.Text()),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("possible_existing_student", sa.Boolean(), nullable=False),
        sa.Column(
            "teacher_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "converted_student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="RESTRICT"),
            unique=True,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("grade BETWEEN 1 AND 11", name="ck_trial_grade"),
        sa.CheckConstraint("source IN ('WEB', 'TELEGRAM')", name="ck_trial_source"),
        sa.CheckConstraint(
            "status IN ('NEW', 'IN_REVIEW', 'RESCHEDULE_REQUESTED', 'CONFIRMED', "
            "'COMPLETED', 'REJECTED', 'CANCELLED')",
            name="ck_trial_status",
        ),
        sa.CheckConstraint(
            "(preferred_start IS NULL AND preferred_end IS NULL) OR "
            "(preferred_start IS NOT NULL AND preferred_end > preferred_start)",
            name="ck_trial_preferred_interval",
        ),
        sa.CheckConstraint(
            "(confirmed_start IS NULL AND confirmed_end IS NULL) OR "
            "(confirmed_start IS NOT NULL AND confirmed_end > confirmed_start)",
            name="ck_trial_confirmed_interval",
        ),
        sa.CheckConstraint(
            "status NOT IN ('CONFIRMED', 'COMPLETED') OR "
            "(teacher_id IS NOT NULL AND confirmed_start IS NOT NULL "
            "AND confirmed_end IS NOT NULL)",
            name="ck_trial_confirmed_has_slot",
        ),
    )
    op.create_index("ix_trial_status_created", "trial_requests", ["status", "created_at"])
    op.execute(
        """
        ALTER TABLE trial_requests ADD CONSTRAINT excl_trial_teacher_overlap
        EXCLUDE USING gist (
            teacher_id WITH =,
            tstzrange(confirmed_start, confirmed_end, '[)') WITH &&
        ) WHERE (status = 'CONFIRMED')
        """
    )


def downgrade() -> None:
    op.drop_table("trial_requests")
    op.drop_table("trial_submission_attempts")
