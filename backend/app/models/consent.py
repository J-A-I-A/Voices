"""ConsentRecord — evidence that a contributor gave explicit consent.

The Privacy Notice commits to two things this table backs:

  * "You give your explicit consent for JAIA to collect and process your voice
    recording and metadata for the purposes described above."
  * "A record of your consent is kept so it can be provided to the Office of
    the Information Commissioner on request."

Records are append-only: withdrawing consent sets `withdrawn_at` on the active
row rather than deleting it, and re-consenting inserts a new row. The full
history is therefore auditable, which is the point of keeping it.
"""
from __future__ import annotations

import datetime as _dt
import enum
import uuid
from typing import Optional

from sqlalchemy import String, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class ConsentChannel(str, enum.Enum):
    whatsapp = "whatsapp"
    portal = "portal"


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Which version of the notice was agreed to, so a later revision does not
    # silently appear to have been accepted.
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    channel: Mapped[ConsentChannel] = mapped_column(Enum(ConsentChannel), nullable=False)

    # What the contributor actually sent, kept verbatim as the evidence.
    evidence: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    whatsapp_message_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    consented_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    withdrawn_at: Mapped[Optional[_dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User")  # type: ignore[name-defined]

    @property
    def is_active(self) -> bool:
        return self.withdrawn_at is None
