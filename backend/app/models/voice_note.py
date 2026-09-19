"""VoiceNote — a user's submitted voice recording linked to a phrase."""
from __future__ import annotations

import enum
import uuid
import datetime as _dt
from typing import Any, Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, Enum, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class VoiceNoteStatus(str, enum.Enum):
    received = "received"
    accepted = "accepted"
    rejected = "rejected"
    needs_review = "needs_review"


class VoiceNote(Base):
    __tablename__ = "voice_notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    phrase_id: Mapped[Optional[str]] = mapped_column(ForeignKey("phrases.id"), nullable=True, index=True)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)  # seconds, rounded
    mime_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[VoiceNoteStatus] = mapped_column(
        Enum(VoiceNoteStatus), nullable=False, default=VoiceNoteStatus.received, index=True
    )
    reject_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qc: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    reviewed_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="voice_notes", foreign_keys=[user_id])  # type: ignore[name-defined]
    phrase: Mapped[Optional["Phrase"]] = relationship("Phrase")  # type: ignore[name-defined]

    @property
    def audio_signed_url(self) -> Optional[str]:
        """Set by the API layer when serializing; not a column."""
        return None

