"""Phrase — the bank of phrases users read aloud (speech/ASR data collection)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class Phrase(Base):
    __tablename__ = "phrases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en-JM")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

