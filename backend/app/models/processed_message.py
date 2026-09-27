"""Record of WhatsApp messages already handled, for idempotency.

Meta's Cloud API delivers webhooks at least once: a delivery that is not
acknowledged promptly is retried with backoff, and duplicates can arrive
regardless. Without a record of what has been handled, every redelivery of the
same inbound message issued another phrase, so contributors received phrases
they never asked for.
"""
from __future__ import annotations

import datetime as _dt

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db import Base


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    # Meta's wamid. Primary key, so a concurrent duplicate delivery loses the
    # insert race rather than being processed twice.
    message_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    processed_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
