"""WhatsApp Cloud API webhook router — the Carib Voices agent.

Inbound handling:
  * verify the X-Hub-Signature-256 signature with the app secret
  * GET handshake with the verify token on subscription
  * process each message id exactly once (the Cloud API retries deliveries)
  * only accept audio (voice) notes + text replies
  * match sender to a verified user by phone number
  * require explicit consent (reply I AGREE) before anything is collected;
    STOP withdraws it
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
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.phrase import Phrase
from ..models.processed_message import ProcessedMessage
from ..models.user import User
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..models.consent import ConsentChannel
from ..services import consent
from ..services.phrase_length import estimated_seconds
from ..services import whatsapp as wa
from ..services.whatsapp import WhatsAppError
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
                # One bad message must not fail the whole delivery. Meta retries
                # any non-2xx response and disables the subscription after
                # repeated failures, so we always acknowledge and log instead.
                try:
                    if not _claim_message(db, msg):
                        continue
                    await _handle_message(msg, contacts.get(msg.get("from")), db)
                except WhatsAppError as e:
                    logger.error(
                        "WhatsApp send failed for message %s from %s: %s",
                        msg.get("id"), msg.get("from"), e,
                    )
                    db.rollback()
                except Exception:
                    logger.exception(
                        "Unhandled error processing message %s from %s",
                        msg.get("id"), msg.get("from"),
                    )
                    db.rollback()
    return {"status": "ok"}



def _claim_message(db: Session, msg: dict) -> bool:
    """Claim an inbound message for processing exactly once.

    The Cloud API delivers at least once — an unacknowledged delivery is
    retried with backoff, so a message can arrive many times (this is how
    contributors ended up receiving phrases they never asked for, hours after
    the fact, once a spell of failing sends stopped 500ing). Inserting the
    message id first means a duplicate loses the primary-key race and is
    skipped.

    Returns True when this delivery should be processed.
    """
    msg_id = msg.get("id")
    if not msg_id:
        # Nothing to deduplicate on; process it rather than dropping it.
        return True

    if db.get(ProcessedMessage, msg_id) is not None:
        logger.info("skipping duplicate delivery of %s", msg_id)
        return False

    try:
        db.add(ProcessedMessage(message_id=msg_id))
        db.commit()
    except IntegrityError:
        # A concurrent delivery of the same message won the race.
        db.rollback()
        logger.info("skipping concurrent duplicate delivery of %s", msg_id)
        return False

    if _is_stale(msg):
        # A retry of something long past. Audio still gets processed — dropping
        # it would lose a contribution — but re-prompting with a phrase for an
        # old "hello" is exactly the unprompted message we want to avoid.
        if msg.get("type") not in ("audio", "voice"):
            logger.info("ignoring stale %s message %s", msg.get("type"), msg_id)
            return False
    return True


def _is_stale(msg: dict) -> bool:
    ts = msg.get("timestamp")
    if not ts:
        return False
    try:
        sent = int(ts)
    except (TypeError, ValueError):
        return False
    age = time.time() - sent
    return age > settings.whatsapp_stale_message_seconds


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

    text_body = (msg.get("text") or {}).get("body")

    # ── Consent gate ────────────────────────────────────────────────────
    # The Privacy Notice states a contributor "will not be able to submit a
    # recording until you have given this confirmation", so this sits ahead of
    # both phrase issuing and audio intake.
    if consent.is_withdrawal(text_body):
        closed = consent.withdraw_consent(db, user, reason="replied STOP on WhatsApp")
        await wa.send_text(
            from_number,
            "Your consent has been withdrawn and we will not collect any new recordings from you. "
            + ("Recordings already published in the open dataset in de-identified form cannot be "
               "recalled, as explained in our Privacy Notice. " if closed else "")
            + "Reply I AGREE at any time if you would like to take part again.",
        )
        return

    if not consent.has_consent(db, user):
        if consent.is_agreement(text_body):
            consent.record_consent(
                db, user,
                channel=ConsentChannel.whatsapp,
                evidence=text_body,
                whatsapp_message_id=msg_id,
                phone=e164,
            )
            await wa.send_text(
                from_number,
                "Thank you — your consent has been recorded. Here comes your first phrase.",
            )
            await _issue_phrase(db, user, from_number)
            return
        # No consent yet: prompt, and accept nothing else (audio included).
        await wa.send_text(from_number, consent.consent_prompt(settings.portal_base_url))
        return

    if msg_type in ("audio", "voice"):
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
    seconds = estimated_seconds(phrase.word_count)
    body = (
        f"Great, {user.first_name}! Here is your phrase.\n\n"
        f"\"{phrase.text}\"\n\n"
        f"This one should take about {seconds:g} seconds to read. "
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
        "Send any message when you'd like another phrase.",
    )
