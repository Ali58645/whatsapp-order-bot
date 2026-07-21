"""Alembic: lead notes + tags for owner CRM.

Revision ID: 0006_lead_notes_tags
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_lead_notes_tags"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Idempotent: a prior hung run may have added columns before stamping.
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("leads")}
    if "notes" not in cols:
        op.add_column("leads", sa.Column("notes", sa.Text(), nullable=False, server_default=""))
    if "tags" not in cols:
        op.add_column(
            "leads",
            sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    op.drop_column("leads", "tags")
    op.drop_column("leads", "notes")
