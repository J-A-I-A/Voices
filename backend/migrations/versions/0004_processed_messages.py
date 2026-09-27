"""Idempotency record for inbound WhatsApp messages.

Revision ID: 0004_processed_messages
Revises: 0003_user_deleted_at
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_processed_messages"
down_revision = "0003_user_deleted_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_messages",
        sa.Column("message_id", sa.String(128), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_processed_messages_processed_at", "processed_messages", ["processed_at"])


def downgrade() -> None:
    op.drop_index("ix_processed_messages_processed_at", table_name="processed_messages")
    op.drop_table("processed_messages")
