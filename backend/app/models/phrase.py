"""Phrase — the bank of phrases users read aloud (speech/ASR data collection)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base

# Storage bound for phrase text. Sized so it can never be the binding limit:
# the real cap is duration (see services.phrase_length), and the longest
# allowed phrase is ~87 words, which even at 20 characters a word is under
# 1,900 characters. This only guards against a pasted document.
PHRASE_TEXT_MAX_CHARS = 2000


class Phrase(Base):
    __tablename__ = "phrases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text: Mapped[str] = mapped_column(String(PHRASE_TEXT_MAX_CHARS), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en-JM")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    # Cached so the bank can be filtered and counted by length band in SQL.
    # Recomputed from `text` on every write — see services.phrase_length.
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

