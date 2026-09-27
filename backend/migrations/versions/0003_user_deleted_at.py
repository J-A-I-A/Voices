"""Add users.deleted_at for self-service profile deletion.

Revision ID: 0003_user_deleted_at
Revises: 0002_admin_and_consent
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_user_deleted_at"
down_revision = "0002_admin_and_consent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
