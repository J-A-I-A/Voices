"""User model.

Note: `date_of_birth` is stored, never a static age. Age is derived at read
time via security.age_from_dob so the 18+ gate stays correct for returning users.
"""
from __future__ import annotations

import enum
import uuid
import datetime as _dt
from typing import Optional

from sqlalchemy import String, Date, Boolean, DateTime, Enum, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class AuthProvider(str, enum.Enum):
    google = "google"
    email = "email"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("whatsapp_number", name="uq_users_whatsapp_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    date_of_birth: Mapped[_dt.date] = mapped_column(Date, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    auth_provider: Mapped[AuthProvider] = mapped_column(Enum(AuthProvider), nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    whatsapp_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_reviewer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    google_subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    # per-user agent session state: the phrase assigned but not yet recorded.
    pending_phrase_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Set when the contributor deletes their own profile. The row survives in
    # scrubbed form so the consent register stays intact (the Privacy Notice
    # commits to producing it on request); every field that identifies a person
    # is cleared, and a deleted account can no longer sign in.
    deleted_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    voice_notes: Mapped[list["VoiceNote"]] = relationship(  # type: ignore[name-defined]
        "VoiceNote",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="VoiceNote.user_id",  # disambiguate from reviewer_id
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

