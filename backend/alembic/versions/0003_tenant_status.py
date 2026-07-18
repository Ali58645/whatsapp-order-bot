"""Add tenants.status for Draft/Live/Paused/Archived lifecycle.

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="live",
        ),
    )
    op.create_index("ix_tenants_status", "tenants", ["status"])


def downgrade() -> None:
    op.drop_index("ix_tenants_status", table_name="tenants")
    op.drop_column("tenants", "status")
