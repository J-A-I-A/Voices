"""Add users.is_admin and the consent_records table.

Revision ID: 0002_admin_and_consent
Revises: 0001_initial
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_admin_and_consent"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

consentchannel_enum = sa.Enum("whatsapp", "portal", name="consentchannel")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Drop the server default so the model's default governs new rows.
    op.alter_column("users", "is_admin", server_default=None)

    # The enum is created implicitly by create_table below; creating it
    # explicitly as well raises DuplicateObject inside the same transaction.
    op.create_table(
        "consent_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("policy_version", sa.String(40), nullable=False),
        sa.Column("channel", consentchannel_enum, nullable=False),
        sa.Column("evidence", sa.String(500), nullable=True),
        sa.Column("whatsapp_message_id", sa.String(128), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")
    consentchannel_enum.drop(op.get_bind(), checkfirst=True)
    op.drop_column("users", "is_admin")
