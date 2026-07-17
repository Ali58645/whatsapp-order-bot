"""Initial schema — all tables.

Revision ID: 0001
Revises:
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _json_type():
    if _is_postgres():
        return postgresql.JSONB()
    return sa.JSON()


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    json_t = postgresql.JSONB() if is_pg else sa.JSON()

    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("phone_number_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("flow_mode", sa.String(16), nullable=False),
        sa.Column("config", json_t, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # ── contacts ─────────────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("wa_id", sa.String(32), nullable=False),
        sa.Column("profile_name", sa.String(256), nullable=False, server_default=""),
        sa.Column(
            "first_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("tenant_id", "wa_id", name="uq_contacts_tenant_wa"),
    )
    op.create_index("ix_contacts_tenant_wa", "contacts", ["tenant_id", "wa_id"])

    # ── sessions ─────────────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("flow_mode", sa.String(16), nullable=False),
        sa.Column("phase", sa.String(32), nullable=False, server_default="GREETING"),
        sa.Column("meta", json_t, nullable=False, server_default="{}"),
        sa.Column("history", json_t, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    # Partial unique index: one active session per (tenant, contact)
    if is_pg:
        op.execute(
            "CREATE UNIQUE INDEX ix_sessions_active_one_per_contact "
            "ON sessions (tenant_id, contact_id) WHERE status = 'active'"
        )
    else:
        op.execute(
            "CREATE UNIQUE INDEX ix_sessions_active_one_per_contact "
            "ON sessions (tenant_id, contact_id) WHERE status = 'active'"
        )

    # ── leads ────────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("business_name", sa.String(256), nullable=False, server_default=""),
        sa.Column("business_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("locations", sa.String(16), nullable=False, server_default=""),
        sa.Column("current_system", sa.String(64), nullable=False, server_default=""),
        sa.Column("demo_slot", sa.String(64), nullable=False, server_default=""),
        sa.Column("entry_intent", sa.String(32), nullable=False, server_default=""),
        sa.Column("ad_source", sa.String(256), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # ── orders ───────────────────────────────────────────────────────────────
    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("items", json_t, nullable=False, server_default="[]"),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivery_address", sa.Text(), nullable=False, server_default=""),
        sa.Column("location_lat", sa.Float(), nullable=True),
        sa.Column("location_lng", sa.Float(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    # ── mutes ────────────────────────────────────────────────────────────────
    op.create_table(
        "mutes",
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), primary_key=True),
        sa.Column("wa_id", sa.String(32), primary_key=True),
        sa.Column("muted_until", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "wa_id", name="uq_mutes_tenant_wa"),
    )

    # ── events ───────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.BigInteger(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("payload", json_t, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()") if is_pg else sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.create_index("ix_events_tenant_created", "events", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("mutes")
    op.drop_table("orders")
    op.drop_table("leads")
    op.drop_table("sessions")
    op.drop_table("contacts")
    op.drop_table("tenants")
