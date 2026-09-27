"""The agent must never message a contributor they did not prompt.

Meta's Cloud API delivers webhooks at least once and retries unacknowledged
deliveries with backoff, so the same inbound message can arrive repeatedly —
sometimes hours later. Each redelivery used to issue another phrase, which is
how contributors received phrases out of the blue.
"""
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.processed_message import ProcessedMessage
from app.models.voice_note import VoiceNote
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)
BOB = "18765550001"


def _sign(body: bytes) -> dict:
    return {
        "X-Hub-Signature-256": "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest(),
        "Content-Type": "application/json",
    }


def _text(body="hello", mid="wamid.SAME", ts=None):
    m = {"from": BOB, "id": mid, "type": "text", "text": {"body": body}}
    m["timestamp"] = str(int(ts if ts is not None else time.time()))
    return m


def _audio(mid="wamid.AUDIO", ts=None):
    m = {"from": BOB, "id": mid, "type": "audio",
         "audio": {"id": "media_1", "mime_type": "audio/ogg"}}
    m["timestamp"] = str(int(ts if ts is not None else time.time()))
    return m


def _post(messages):
    body = json.dumps({
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"value": {
            "messaging_product": "whatsapp",
            "contacts": [{"wa_id": BOB, "name": "Bob"}],
            "messages": messages,
        }}]}],
    }).encode()
    return client.post("/whatsapp/webhook", content=body, headers=_sign(body))


@pytest.fixture
def sent(monkeypatch):
    out = []
    import app.services.whatsapp as wasvc

    async def fake_send(num, body):
        out.append(body)
        return {}

    monkeypatch.setattr(wasvc, "send_text", fake_send)
    return out


def _assign_pending_phrase():
    """A voice note is only stored against the phrase the user was asked to read."""
    from app.models.phrase import Phrase
    from app.models.user import User
    s = Session()
    try:
        u = s.query(User).filter(User.whatsapp_number == "+" + BOB).first()
        u.pending_phrase_id = s.query(Phrase).first().id
        s.commit()
    finally:
        s.close()


@pytest.fixture
def audio_stack(monkeypatch):
    """Stub media download, S3 upload and QC so audio handling runs offline."""
    import app.routers.whatsapp as war

    async def fake_fetch(media_id):
        return b"OggS-fake-audio", "audio/ogg"

    async def noop_enqueue(note_id):
        return None

    monkeypatch.setattr(war.wa, "fetch_media_bytes", fake_fetch)
    monkeypatch.setattr(war, "upload_bytes", lambda *a, **k: None)
    monkeypatch.setattr(war, "enqueue_qc", noop_enqueue)


# ─── The bug ────────────────────────────────────────────────────────────
def test_redelivery_does_not_send_a_second_phrase(sent, consented_bob):
    """The same message id arriving twice must produce one reply, not two."""
    _post([_text()])
    assert len(sent) == 1

    _post([_text()])  # Meta retries the identical delivery
    assert len(sent) == 1, f"redelivery sent an unprompted message: {sent}"


def test_many_redeliveries_still_send_once(sent, consented_bob):
    for _ in range(5):
        _post([_text()])
    assert len(sent) == 1


def test_duplicate_within_one_payload_is_handled_once(sent, consented_bob):
    _post([_text(mid="wamid.DUP"), _text(mid="wamid.DUP")])
    assert len(sent) == 1


def test_distinct_messages_each_get_a_reply(sent, consented_bob):
    """Deduplication must not swallow genuine new messages."""
    _post([_text(mid="wamid.ONE")])
    _post([_text(mid="wamid.TWO")])
    assert len(sent) == 2


def test_redelivered_audio_is_not_stored_twice(sent, consented_bob, audio_stack):
    _assign_pending_phrase()
    _post([_audio()])
    _post([_audio()])

    s = Session()
    try:
        assert s.query(VoiceNote).count() == 1, "the same recording was stored twice"
    finally:
        s.close()


def test_message_id_is_recorded():
    _post([_text(mid="wamid.TRACKED")])
    s = Session()
    try:
        assert s.get(ProcessedMessage, "wamid.TRACKED") is not None
    finally:
        s.close()


# ─── Stale retries ──────────────────────────────────────────────────────
def test_stale_text_retry_is_ignored(sent, consented_bob):
    """An old 'hello' replayed hours later must not trigger a phrase."""
    old = time.time() - (settings.whatsapp_stale_message_seconds + 600)
    _post([_text(mid="wamid.OLD", ts=old)])
    assert sent == [], f"stale retry produced an unprompted message: {sent}"


def test_recent_message_is_not_treated_as_stale(sent, consented_bob):
    _post([_text(mid="wamid.FRESH", ts=time.time() - 5)])
    assert len(sent) == 1


def test_message_without_a_timestamp_is_still_processed(sent, consented_bob):
    m = {"from": BOB, "id": "wamid.NOTS", "type": "text", "text": {"body": "hi"}}
    _post([m])
    assert len(sent) == 1


def test_stale_audio_is_still_stored(sent, consented_bob, audio_stack):
    """Dropping a late voice note would lose a contribution, so audio survives."""
    _assign_pending_phrase()
    old = time.time() - (settings.whatsapp_stale_message_seconds + 600)
    _post([_audio(mid="wamid.OLDAUDIO", ts=old)])

    s = Session()
    try:
        assert s.query(VoiceNote).count() == 1
    finally:
        s.close()
