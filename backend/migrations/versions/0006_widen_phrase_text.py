"""Widen phrases.text so phrase duration, not storage, is the binding limit.

500 characters could reject a phrase that was still within the 35-second
reading limit when its words happened to be long.

Revision ID: 0006_widen_phrase_text
Revises: 0005_phrase_word_count
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_widen_phrase_text"
down_revision = "0005_phrase_word_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("phrases", "text",
                    existing_type=sa.String(500), type_=sa.String(2000),
                    existing_nullable=False)


def downgrade() -> None:
    # Truncate anything that would no longer fit, otherwise the narrowing fails.
    op.execute("UPDATE phrases SET text = LEFT(text, 500) WHERE LENGTH(text) > 500")
    op.alter_column("phrases", "text",
                    existing_type=sa.String(2000), type_=sa.String(500),
                    existing_nullable=False)
