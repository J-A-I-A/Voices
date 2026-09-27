"""Consent lifecycle: grant, check, withdraw.

Backs the Privacy Notice's promise that a contributor gives explicit consent
before submitting a recording, and that the record can be produced on request.
"""
from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.consent import ConsentChannel, ConsentRecord
from ..models.user import User

logger = logging.getLogger("carib.consent")

# What a contributor may reply over WhatsApp to give consent. Matched on the
# whole message (case-insensitive, punctuation and spacing tolerated) so a
# passing mention of the word inside a sentence is never read as agreement.
_AGREE_PATTERN = re.compile(r"^\s*(i\s*agree|agree|yes\s*,?\s*i\s*agree|accept|i\s*consent)\s*[.!]*\s*$", re.I)
_WITHDRAW_PATTERN = re.compile(r"^\s*(stop|withdraw|withdraw\s*consent|delete\s*my\s*data|unsubscribe)\s*[.!]*\s*$", re.I)


def is_agreement(text: Optional[str]) -> bool:
    return bool(text and _AGREE_PATTERN.match(text))


def is_withdrawal(text: Optional[str]) -> bool:
    return bool(text and _WITHDRAW_PATTERN.match(text))


def active_consent(db: Session, user: User) -> Optional[ConsentRecord]:
    """The user's current consent for the *current* policy version, if any.

    Consent to an older version of the notice does not carry forward; bumping
    PRIVACY_POLICY_VERSION re-prompts everyone.
    """
    return (
        db.query(ConsentRecord)
        .filter(
            ConsentRecord.user_id == user.id,
            ConsentRecord.withdrawn_at.is_(None),
            ConsentRecord.policy_version == settings.privacy_policy_version,
        )
        .order_by(ConsentRecord.consented_at.desc())
        .first()
    )


def has_consent(db: Session, user: User) -> bool:
    return active_consent(db, user) is not None


def record_consent(
    db: Session,
    user: User,
    *,
    channel: ConsentChannel,
    evidence: Optional[str] = None,
    whatsapp_message_id: Optional[str] = None,
    phone: Optional[str] = None,
) -> ConsentRecord:
    """Store consent. Idempotent: returns the existing record if already active."""
    existing = active_consent(db, user)
    if existing:
        return existing
    rec = ConsentRecord(
        user_id=user.id,
        policy_version=settings.privacy_policy_version,
        channel=channel,
        evidence=(evidence or "")[:500] or None,
        whatsapp_message_id=whatsapp_message_id,
        phone=phone or user.whatsapp_number,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    logger.info(
        "consent recorded for user %s via %s (policy %s)",
        user.id, channel.value, settings.privacy_policy_version,
    )
    return rec


def withdraw_consent(db: Session, user: User, *, reason: Optional[str] = None) -> int:
    """Mark every active consent row withdrawn. Returns how many were closed."""
    now = _dt.datetime.now(_dt.timezone.utc)
    rows = (
        db.query(ConsentRecord)
        .filter(ConsentRecord.user_id == user.id, ConsentRecord.withdrawn_at.is_(None))
        .all()
    )
    for r in rows:
        r.withdrawn_at = now
        if reason:
            r.evidence = ((r.evidence or "") + f" | withdrawn: {reason}")[:500]
    if rows:
        db.commit()
        logger.info("consent withdrawn for user %s (%d record(s))", user.id, len(rows))
    return len(rows)


def consent_prompt(portal_base_url: str) -> str:
    """The message the agent sends before accepting a first recording."""
    return (
        "Before you send a voice note, we need your consent.\n\n"
        "Carib Voices is a project of the Jamaica Artificial Intelligence Association (JAIA). "
        "Your voice recordings and optional metadata (region, age range) will be published in a "
        "de-identified open dataset used for AI model training and linguistic research. "
        "Your phone number is never published.\n\n"
        f"Full Privacy Notice: {portal_base_url}/privacy\n\n"
        "Participation is voluntary and you can withdraw at any time by replying STOP. "
        "Note that recordings already published in the open dataset cannot be recalled.\n\n"
        "Reply *I AGREE* to give your consent and start recording."
    )
