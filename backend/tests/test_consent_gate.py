"""The agent must collect nothing until the contributor has consented.

Privacy Notice: "You will not be able to submit a recording until you have
given this confirmation." These tests hold the code to that.
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.consent import ConsentRecord
from app.models.user import User
from app.services import consent as consent_svc
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)
BOB = "18765550001"


def _sign(body: bytes) -> dict:
    return {
        "X-Hub-Signature-256": "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest(),
        "Content-Type": "application/json",
    }


def _envelope(messages):
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [
        {"value": {"messaging_product": "whatsapp",
                   "contacts": [{"wa_id": BOB, "name": "Bob"}],
                   "messages": messages}}]}]}


def _text(body, mid="abc"):
    return {"from": BOB, "id": "wamid." + mid, "type": "text", "text": {"body": body}}


def _audio(mid="aud"):
    return {"from": BOB, "id": "wamid." + mid, "type": "audio",
            "audio": {"id": "media_1", "mime_type": "audio/ogg"}}


def _post(messages):
    body = json.dumps(_envelope(messages)).encode()
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


def _bob():
    s = Session()
    try:
        return s.query(User).filter(User.whatsapp_number == "+" + BOB).first()
    finally:
        s.close()


# ─── Gate ───────────────────────────────────────────────────────────────
def test_first_contact_asks_for_consent_not_a_phrase(sent):
    r = _post([_text("hi")])
    assert r.status_code == 200
    joined = " ".join(sent).lower()
    assert "consent" in joined and "i agree" in joined
    assert "here is your phrase" not in joined


def test_audio_is_refused_before_consent(sent, monkeypatch):
    """A recording sent without consent must never reach S3."""
    uploaded = []
    import app.routers.whatsapp as war
    monkeypatch.setattr(war, "upload_bytes", lambda *a, **k: uploaded.append(a))

    r = _post([_audio()])
    assert r.status_code == 200
    assert uploaded == [], "audio was stored despite no consent on file"
    assert "consent" in " ".join(sent).lower()

    s = Session()
    try:
        from app.models.voice_note import VoiceNote
        assert s.query(VoiceNote).count() == 0
    finally:
        s.close()


def test_i_agree_records_consent_and_issues_a_phrase(sent):
    r = _post([_text("I AGREE")])
    assert r.status_code == 200

    s = Session()
    try:
        rec = s.query(ConsentRecord).filter(ConsentRecord.user_id == _bob().id).one()
        assert rec.withdrawn_at is None
        assert rec.evidence == "I AGREE"
        assert rec.policy_version == settings.privacy_policy_version
        assert rec.channel.value == "whatsapp"
        assert rec.whatsapp_message_id == "wamid.abc"
    finally:
        s.close()

    joined = " ".join(sent).lower()
    assert "consent has been recorded" in joined
    assert "phrase" in joined


def test_consent_is_not_reconsumed_on_later_messages(sent):
    _post([_text("I AGREE", mid="one")])
    _post([_text("another message", mid="two")])
    s = Session()
    try:
        assert s.query(ConsentRecord).count() == 1, "a second record was written"
    finally:
        s.close()


def test_stop_withdraws_consent(sent):
    _post([_text("I AGREE", mid="one")])
    r = _post([_text("STOP", mid="two")])
    assert r.status_code == 200

    s = Session()
    try:
        rec = s.query(ConsentRecord).one()
        assert rec.withdrawn_at is not None
    finally:
        s.close()
    assert "withdrawn" in " ".join(sent).lower()


def test_withdrawn_user_is_gated_again(sent):
    _post([_text("I AGREE", mid="one")])
    _post([_text("STOP", mid="two")])
    sent.clear()
    _post([_text("give me a phrase", mid="three")])
    assert "i agree" in " ".join(sent).lower()


def test_bumping_the_policy_version_reprompts(sent, monkeypatch):
    """Consent to an older notice must not be treated as consent to a new one."""
    _post([_text("I AGREE", mid="one")])
    monkeypatch.setattr(settings, "privacy_policy_version", "2027-01-01")
    sent.clear()
    _post([_text("hello", mid="two")])
    assert "i agree" in " ".join(sent).lower()


# ─── Matching ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("text", ["I AGREE", "i agree", " I Agree. ", "agree", "I consent", "accept"])
def test_agreement_phrasings(text):
    assert consent_svc.is_agreement(text)


@pytest.mark.parametrize("text", [
    "I do not agree",
    "why do I agree to this?",
    "agreement",
    "",
    None,
])
def test_non_agreements_are_not_consent(text):
    """A passing mention inside a sentence must never count as consent."""
    assert not consent_svc.is_agreement(text)


@pytest.mark.parametrize("text", ["STOP", "stop", "withdraw", "delete my data"])
def test_withdrawal_phrasings(text):
    assert consent_svc.is_withdrawal(text)
