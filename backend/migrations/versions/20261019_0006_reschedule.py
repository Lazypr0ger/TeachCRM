"""Add atomic lesson reschedule workflow."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0006"
down_revision = "20261019_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reschedule_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "lesson_id",
            sa.Uuid(),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            sa.Uuid(),
            sa.ForeignKey("student_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("counter_starts_at", sa.DateTime(timezone=True)),
        sa.Column("counter_ends_at", sa.DateTime(timezone=True)),
        sa.Column("response_note", sa.Text()),
        sa.Column("responded_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "proposed_ends_at > proposed_starts_at", name="ck_reschedule_proposed_interval"
        ),
        sa.CheckConstraint(
            "counter_starts_at IS NULL OR counter_ends_at > counter_starts_at",
            name="ck_reschedule_counter_interval",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'COUNTER_OFFER', 'ACCEPTED', 'REJECTED', 'CANCELLED')",
            name="ck_reschedule_status",
        ),
    )
    op.create_index(
        "ix_reschedule_student_created",
        "reschedule_requests",
        ["student_id", "created_at"],
    )
    op.create_index("ix_reschedule_status_created", "reschedule_requests", ["status", "created_at"])
    op.create_index(
        "uq_reschedule_active_lesson",
        "reschedule_requests",
        ["lesson_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'COUNTER_OFFER')"),
    )


def downgrade() -> None:
    op.drop_table("reschedule_requests")
