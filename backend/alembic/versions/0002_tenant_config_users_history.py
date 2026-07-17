"""Tenant config history, users, tenants.updated_at.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    json_t = postgresql.JSONB() if is_pg else sa.JSON()
    ts_default = sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP")

    op.add_column(
        "tenants",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
    )

    op.create_table(
        "config_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("config", json_t, nullable=False),
        sa.Column("changed_by", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
    )
    op.create_index("ix_config_history_tenant_id", "config_history", ["tenant_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=ts_default, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("config_history")
    op.drop_column("tenants", "updated_at")
