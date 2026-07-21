"""Add channel dimension to contacts, sessions, leads, orders, events, mutes.

Revision ID: 0005
Revises: 0004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column("channel", sa.String(16), nullable=False, server_default="whatsapp"),
    )
    op.drop_constraint("uq_contacts_tenant_wa", "contacts", type_="unique")
    op.create_unique_constraint(
        "uq_contacts_tenant_channel_wa",
        "contacts",
        ["tenant_id", "channel", "wa_id"],
    )

    for table in ("sessions", "leads", "orders"):
        op.add_column(
            table,
            sa.Column("channel", sa.String(16), nullable=False, server_default="whatsapp"),
        )

    op.add_column(
        "events",
        sa.Column("channel", sa.String(16), nullable=True),
    )

    op.add_column(
        "mutes",
        sa.Column("channel", sa.String(16), nullable=False, server_default="whatsapp"),
    )
    op.drop_constraint("uq_mutes_tenant_wa", "mutes", type_="unique")
    op.create_unique_constraint(
        "uq_mutes_tenant_channel_wa",
        "mutes",
        ["tenant_id", "channel", "wa_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_mutes_tenant_channel_wa", "mutes", type_="unique")
    op.create_unique_constraint("uq_mutes_tenant_wa", "mutes", ["tenant_id", "wa_id"])
    op.drop_column("mutes", "channel")

    op.drop_column("events", "channel")
    for table in ("orders", "leads", "sessions"):
        op.drop_column(table, "channel")

    op.drop_constraint("uq_contacts_tenant_channel_wa", "contacts", type_="unique")
    op.create_unique_constraint("uq_contacts_tenant_wa", "contacts", ["tenant_id", "wa_id"])
    op.drop_column("contacts", "channel")
