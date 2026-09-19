"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

# postgresql.ENUM honors create_type, unlike the generic sa.Enum (which silently
# drops it and always auto-creates on table-create, causing DuplicateObject).
authprovider_enum = postgresql.ENUM("google", "email", name="authprovider", create_type=False)
voicenotestatus_enum = postgresql.ENUM(
    "received", "accepted", "rejected", "needs_review",
    name="voicenotestatus", create_type=False,
)


def upgrade() -> None:
    # Create the named enum types explicitly (checkfirst -> safe to re-run after
    # a partial failure). create_type=False above means op.create_table will NOT
    # also try to CREATE TYPE and collide.
    authprovider_enum.create(op.get_bind(), checkfirst=True)
    voicenotestatus_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("auth_provider", authprovider_enum, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("whatsapp_number", sa.String(20), nullable=True),
        sa.Column("whatsapp_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_reviewer", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("google_subject", sa.String(255), nullable=True),
        sa.Column("pending_phrase_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("whatsapp_number", name="uq_users_whatsapp_number"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_google_subject", "users", ["google_subject"])

    op.create_table(
        "phrases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False, server_default="en-JM"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_phrases_active", "phrases", ["active"])

    op.create_table(
        "verification_codes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_verification_codes_user_id", "verification_codes", ["user_id"])
    op.create_index("ix_verification_codes_phone", "verification_codes", ["phone"])

    op.create_table(
        "voice_notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("phrase_id", sa.String(36), sa.ForeignKey("phrases.id"), nullable=True),
        sa.Column("whatsapp_message_id", sa.String(128), nullable=True),
        sa.Column("s3_key", sa.String(512), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("mime_type", sa.String(80), nullable=True),
        sa.Column("status", voicenotestatus_enum, nullable=False, server_default="received"),
        sa.Column("reject_reason", sa.String(255), nullable=True),
        sa.Column("qc", sa.JSON, nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_voice_notes_user_id", "voice_notes", ["user_id"])
    op.create_index("ix_voice_notes_phrase_id", "voice_notes", ["phrase_id"])
    op.create_index("ix_voice_notes_status", "voice_notes", ["status"])
    op.create_index("ix_voice_notes_whatsapp_message_id", "voice_notes", ["whatsapp_message_id"])


def downgrade() -> None:
    op.drop_index("ix_voice_notes_whatsapp_message_id", table_name="voice_notes")
    op.drop_index("ix_voice_notes_status", table_name="voice_notes")
    op.drop_index("ix_voice_notes_phrase_id", table_name="voice_notes")
    op.drop_index("ix_voice_notes_user_id", table_name="voice_notes")
    op.drop_table("voice_notes")

    op.drop_index("ix_verification_codes_phone", table_name="verification_codes")
    op.drop_index("ix_verification_codes_user_id", table_name="verification_codes")
    op.drop_table("verification_codes")

    op.drop_index("ix_phrases_active", table_name="phrases")
    op.drop_table("phrases")

    op.drop_index("ix_users_google_subject", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    voicenotestatus_enum.drop(op.get_bind(), checkfirst=True)
    authprovider_enum.drop(op.get_bind(), checkfirst=True)
