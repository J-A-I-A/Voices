"""Add phrases.word_count and backfill it.

Revision ID: 0005_phrase_word_count
Revises: 0004_processed_messages
"""
from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "0005_phrase_word_count"
down_revision = "0004_processed_messages"
branch_labels = None
depends_on = None

_WORD_RE = re.compile(r"[\w'’]+", re.UNICODE)


def upgrade() -> None:
    op.add_column("phrases", sa.Column("word_count", sa.Integer(), nullable=False,
                                       server_default="0"))
    op.alter_column("phrases", "word_count", server_default=None)

    # Backfill in Python so the count matches the application's tokenizer
    # exactly rather than approximating it in SQL.
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, text FROM phrases")).fetchall()
    for pid, text in rows:
        conn.execute(
            sa.text("UPDATE phrases SET word_count = :wc WHERE id = :id"),
            {"wc": len(_WORD_RE.findall(text or "")), "id": pid},
        )

    op.create_index("ix_phrases_word_count", "phrases", ["word_count"])


def downgrade() -> None:
    op.drop_index("ix_phrases_word_count", table_name="phrases")
    op.drop_column("phrases", "word_count")
