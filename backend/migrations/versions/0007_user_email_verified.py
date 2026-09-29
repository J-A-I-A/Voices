"""Add users.email_verified.

Google accounts are marked verified (Google has already confirmed the
address); existing email/password accounts start unverified and are asked to
confirm via the mailed link.

Revision ID: 0007_user_email_verified
Revises: 0006_widen_phrase_text
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_user_email_verified"
down_revision = "0006_widen_phrase_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE users SET email_verified = true WHERE auth_provider = 'google'")


def downgrade() -> None:
    op.drop_column("users", "email_verified")
