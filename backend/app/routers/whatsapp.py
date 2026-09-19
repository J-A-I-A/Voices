"""WhatsApp Cloud API webhook router — the Carib Voices agent.

Inbound handling:
  * verify the X-Hub-Signature-256 signature with the app secret
  * GET handshake with the verify token on subscription
  * only accept audio (voice) notes + text replies
  * match sender to a verified user by phone number
  * assign a fresh active phrase on each prompt, store pending_phrase_id
  * on a voice note: fetch media, upload to S3, create a received
    VoiceNote, enqueue QC, and reply with a confirmation
  * non-audio replies re-send instructions
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import random
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.phrase import Phrase
from ..models.user import User
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..services import whatsapp as wa
from ..services.rate_limit import hit_rate_limit
from ..services.s3 import upload_bytes
from ..workers.qc_queue import enqueue_qc

logger = logging.getLogger("carib.whatsapp")
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not settings.whatsapp_app_secret:
        return True  # dev convenience; set the secret in prod.
    if not signature_header:
        return False
    expected = "sha256=" + hmac.new(
        settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@router.get("/webhook")
async def webhook_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
):
    """Meta subscription handshake."""
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return int(hub_challenge) if hub_challenge and hub_challenge.lstrip("-").isdigit() else 0
    raise HTTPException(status_code=403, detail="Verify token mismatch.")


@router.post("/webhook")
async def webhook_receive(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_signature(raw, sig):
        raise HTTPException(status_code=401, detail="Invalid signature.")

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored"}

    if payload.get("object") != "whatsapp_business_account":
        return {"status": "ignored"}

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages") or []
            contacts = {c.get("wa_id"): c for c in (value.get("contacts") or [])}
            for msg in messages:
                await _handle_message(msg, contacts.get(msg.get("from")), db)
    return {"status": "ok"}


async def _handle_message(msg: dict, contact: dict | None, db: Session) -> None:
    from_number = msg.get("from")  # digits-only, no '+'
    msg_type = msg.get("type")
    msg_id = msg.get("id")

    if not from_number:
        return
    # Rate-limit per sender to protect the agent.
    if hit_rate_limit(f"wa_in:{from_number}", 20, 60):
        await wa.send_text(from_number, "You're sending messages too quickly. Please slow down.")
        return

    e164 = "+" + from_number
    user = db.query(User).filter(User.whatsapp_number == e164, User.whatsapp_verified.is_(True)).first()

    if not user:
        await wa.send_text(
            from_number,
            "Welcome to Carib Voices! I only talk to verified members. "
            f"Please register and verify your WhatsApp number at {settings.portal_base_url} to get started.",
        )
        return

    if msg_type == "audio":
        await _handle_audio(msg, user, from_number, db)
    elif msg_type == "voice":
        await _handle_audio(msg, user, from_number, db)
    else:
        # Anything that isn't audio -> (re)issue a phrase.
        await _issue_phrase(db, user, from_number)


async def _issue_phrase(db: Session, user: User, from_number: str) -> None:
    phrases = db.query(Phrase).filter(Phrase.active.is_(True)).all()
    if not phrases:
        await wa.send_text(from_number, "No phrases are configured yet. Please try again later.")
        return
    phrase = random.choice(phrases)
    user.pending_phrase_id = phrase.id
    db.commit()
    body = (
        f"Great, {user.first_name}! Here is your phrase.\n\n"
        f"\"{phrase.text}\"\n\n"
        f"Record yourself reading it aloud and send it back as a voice note. "
        f"Make sure you're in a quiet spot and hold the phone close. One take, please!"
    )
    await wa.send_text(from_number, body)


async def _handle_audio(msg: dict, user: User, from_number: str, db: Session) -> None:
    audio = msg.get("audio") or msg.get("voice") or {}
    media_id = audio.get("id")
    mime = audio.get("mime_type") or "audio/ogg"
    if not media_id:
        await wa.send_text(from_number, "I couldn't read that voice note. Please try sending it again.")
        return

    # Resolve pending phrase (the one the user was asked to read).
    phrase_id = user.pending_phrase_id
    if not phrase_id:
        await _issue_phrase(db, user, from_number)
        await wa.send_text(
            from_number,
            "I sent you a phrase — please read it aloud as a voice note.",
        )
        return

    try:
        data, mime = await wa.fetch_media_bytes(media_id)
    except Exception as e:
        logger.exception("media download failed: %s", e)
        await wa.send_text(from_number, "I couldn't download your voice note. Please send it again.")
        return

    key = f"voicenotes/{user.id}/{uuid.uuid4()}.ogg"
    try:
        upload_bytes(key, data, mime_type=mime)
    except Exception as e:
        logger.exception("s3 upload failed: %s", e)
        await wa.send_text(from_number, "Something went wrong saving your note. Please try again.")
        return

    msg_id = msg.get("id")
    note = VoiceNote(
        user_id=user.id,
        phrase_id=phrase_id,
        whatsapp_message_id=msg_id,
        s3_key=key,
        mime_type=mime,
        status=VoiceNoteStatus.received,
        qc=None,
    )
    db.add(note)
    user.pending_phrase_id = None  # consume the phrase
    db.commit()
    db.refresh(note)

    try:
        await enqueue_qc(note.id)
    except Exception as e:
        logger.exception("qc enqueue failed (note %s): %s", note.id, e)

    await wa.send_text(
        from_number,
        "Got it — your voice note was received and is being checked. "
        "I'll let you know the status once quality control is done. "
        "Send any message when you'd like another phrase.",
    )
