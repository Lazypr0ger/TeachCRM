"""Add private file metadata and upload tickets."""

import sqlalchemy as sa
from alembic import op

revision = "20261019_0007"
down_revision = "20261019_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_upload_tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("declared_byte_size", sa.Integer(), nullable=False),
        sa.Column("detected_mime_type", sa.String(120)),
        sa.Column("actual_byte_size", sa.Integer()),
        sa.Column("checksum_sha256", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("completed_file_id", sa.Uuid()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('LESSON_MATERIAL', 'ASSIGNMENT_MATERIAL', 'HOMEWORK')",
            name="ck_file_ticket_purpose",
        ),
        sa.CheckConstraint(
            "status IN ('INITIATED', 'UPLOADED', 'COMPLETED')",
            name="ck_file_ticket_status",
        ),
    )
    op.create_index(
        "ix_file_ticket_owner_status",
        "file_upload_tickets",
        ["owner_user_id", "status"],
    )
    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("byte_size > 0", name="ck_files_positive_size"),
        sa.CheckConstraint(
            "purpose IN ('LESSON_MATERIAL', 'ASSIGNMENT_MATERIAL', 'HOMEWORK')",
            name="ck_files_purpose",
        ),
    )
    op.create_foreign_key(
        "fk_file_ticket_completed_file",
        "file_upload_tickets",
        "files",
        ["completed_file_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "file_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Uuid(),
            sa.ForeignKey("files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.UniqueConstraint("file_id", "entity_type", "entity_id", name="uq_file_link_target"),
    )
    op.create_index("ix_file_links_target", "file_links", ["entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("file_links")
    op.drop_constraint("fk_file_ticket_completed_file", "file_upload_tickets", type_="foreignkey")
    op.drop_table("files")
    op.drop_table("file_upload_tickets")
