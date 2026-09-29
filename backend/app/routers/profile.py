"""Self-service profile management.

Implements the rights the Privacy Notice grants contributors directly, so they
do not have to email the DPO for routine changes:

  * "Access, rectify, or delete your data."
  * "Withdraw your consent at any time."

Deleting a profile scrubs every identifying field and removes the recordings,
but keeps the (now anonymous) consent rows, because the notice also commits to
producing a consent record for the Office of the Information Commissioner.
"""
from __future__ import annotations

import datetime as _dt
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.consent import ConsentRecord
from ..models.user import User
from ..models.voice_note import VoiceNote
from ..schemas.auth import UserOut
from ..security.age import is_at_least_18
from ..security.deps import get_current_user
from ..services import consent as consent_svc
from ..services.s3 import delete_key

logger = logging.getLogger("carib.profile")
router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdate(BaseModel):
    first_name: Optional[str] = Field(None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(None, min_length=1, max_length=120)
    date_of_birth: Optional[_dt.date] = None


class ConsentStatus(BaseModel):
    has_consent: bool
    policy_version: Optional[str] = None
    consented_at: Optional[_dt.datetime] = None
    channel: Optional[str] = None


class DeleteResult(BaseModel):
    deleted: bool
    notes_deleted: int
    audio_objects_deleted: int
    consents_withdrawn: int
    note: str


def _out(user: User) -> UserOut:
    return UserOut(
        id=user.id, first_name=user.first_name, last_name=user.last_name,
        date_of_birth=user.date_of_birth, email=user.email,
        auth_provider=user.auth_provider.value, whatsapp_number=user.whatsapp_number,
        whatsapp_verified=user.whatsapp_verified, email_verified=user.email_verified,
        is_reviewer=user.is_reviewer,
        is_admin=user.is_admin, requires_completion=not bool(user.date_of_birth),
    )


# ─── Rectify ────────────────────────────────────────────────────────────
@router.patch("", response_model=UserOut)
async def update_profile(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Correct your name or date of birth."""
    if body.first_name is not None:
        user.first_name = body.first_name.strip()
    if body.last_name is not None:
        user.last_name = body.last_name.strip()
    if body.date_of_birth is not None:
        # The 18+ gate is enforced here too, not just at registration.
        if not is_at_least_18(body.date_of_birth):
            raise HTTPException(
                status_code=403,
                detail="You must be 18 or older to contribute to Carib Voices.",
            )
        user.date_of_birth = body.date_of_birth
    db.commit()
    db.refresh(user)
    return _out(user)


# ─── WhatsApp number ────────────────────────────────────────────────────
@router.delete("/whatsapp", response_model=UserOut)
async def unlink_whatsapp(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unlink the WhatsApp number.

    Existing recordings are kept — they are already part of the dataset and
    the contributor consented to them. Use DELETE /profile to remove those.
    """
    if not user.whatsapp_number:
        raise HTTPException(status_code=400, detail="No WhatsApp number is linked to this account.")
    logger.info("user %s unlinked their WhatsApp number", user.id)
    user.whatsapp_number = None
    user.whatsapp_verified = False
    user.pending_phrase_id = None  # no dangling phrase assignment
    db.commit()
    db.refresh(user)
    return _out(user)


# ─── Consent ────────────────────────────────────────────────────────────
@router.get("/consent", response_model=ConsentStatus)
async def consent_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = consent_svc.active_consent(db, user)
    if not rec:
        return ConsentStatus(has_consent=False)
    return ConsentStatus(
        has_consent=True,
        policy_version=rec.policy_version,
        consented_at=rec.consented_at,
        channel=rec.channel.value if hasattr(rec.channel, "value") else str(rec.channel),
    )


@router.post("/consent/withdraw", response_model=ConsentStatus)
async def withdraw_consent(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Withdraw consent. No new recordings will be collected."""
    closed = consent_svc.withdraw_consent(db, user, reason="withdrawn by the contributor in the portal")
    if not closed:
        raise HTTPException(status_code=400, detail="You have no active consent to withdraw.")
    # Stop the agent mid-flow as well.
    user.pending_phrase_id = None
    db.commit()
    return ConsentStatus(has_consent=False)


# ─── Delete ─────────────────────────────────────────────────────────────
@router.delete("", response_model=DeleteResult)
async def delete_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the profile: recordings removed, identity scrubbed, consent closed.

    The row itself is retained in anonymous form so the consent register — which
    the Privacy Notice promises to produce on request — is not falsified by the
    deletion. Nothing identifying survives, and the account can no longer sign in.
    """
    if user.deleted_at is not None:
        raise HTTPException(status_code=400, detail="This profile is already deleted.")

    consents = consent_svc.withdraw_consent(db, user, reason="profile deleted by the contributor")

    notes = db.query(VoiceNote).filter(VoiceNote.user_id == user.id).all()
    objects = 0
    for n in notes:
        if n.s3_key:
            try:
                delete_key(n.s3_key)
                objects += 1
            except Exception as e:
                logger.error("could not delete %s during profile deletion: %s", n.s3_key, e)
        db.delete(n)

    # Scrub identity. The email must stay unique, so it becomes an opaque,
    # non-routable placeholder rather than being blanked.
    user.deleted_at = _dt.datetime.now(_dt.timezone.utc)
    user.first_name = "Deleted"
    user.last_name = "user"
    user.email = f"deleted+{uuid.uuid4().hex}@invalid"
    user.password_hash = None
    user.google_subject = None
    user.whatsapp_number = None
    user.whatsapp_verified = False
    user.pending_phrase_id = None
    user.is_reviewer = False
    user.is_admin = False

    # The consent rows stay, but must not carry a phone number any more.
    for rec in db.query(ConsentRecord).filter(ConsentRecord.user_id == user.id).all():
        rec.phone = None

    db.commit()
    logger.info("profile %s deleted by the contributor (%d notes removed)", user.id, len(notes))

    return DeleteResult(
        deleted=True,
        notes_deleted=len(notes),
        audio_objects_deleted=objects,
        consents_withdrawn=consents,
        note=("Your recordings and personal details have been removed. An anonymous consent "
              "record is retained so we can evidence that consent was given and withdrawn. "
              "Recordings already published in a released open dataset cannot be recalled."),
    )
