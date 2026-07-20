"""Add access_logs for admin support / impersonation audit.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "access_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("admin_username", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("tenant_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_access_logs_created", "access_logs", ["created_at"])
    op.create_index("ix_access_logs_admin", "access_logs", ["admin_username"])
    op.create_index("ix_access_logs_tenant", "access_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_access_logs_tenant", table_name="access_logs")
    op.drop_index("ix_access_logs_admin", table_name="access_logs")
    op.drop_index("ix_access_logs_created", table_name="access_logs")
    op.drop_table("access_logs")
