"""Add editable public site settings."""

import sqlalchemy as sa
from alembic import op

revision = "20261020_0016"
down_revision = "20261020_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "site_settings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("singleton_key", sa.Integer(), nullable=False, unique=True),
        sa.Column("brand_name", sa.String(120), nullable=False),
        sa.Column("tagline", sa.String(300)),
        sa.Column("about_text", sa.Text()),
        sa.Column("directions", sa.JSON(), nullable=False),
        sa.Column("advantages", sa.JSON(), nullable=False),
        sa.Column("confirmed_results", sa.JSON(), nullable=False),
        sa.Column("pricing_text", sa.Text()),
        sa.Column("privacy_text", sa.Text()),
        sa.Column("trials_enabled", sa.Boolean(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column(
            "updated_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("singleton_key = 1", name="ck_site_settings_singleton"),
    )


def downgrade() -> None:
    op.drop_table("site_settings")
