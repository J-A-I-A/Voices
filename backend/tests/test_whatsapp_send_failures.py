"""A failing Graph send must not become a 500 for Meta.

Meta retries any non-2xx webhook response and disables the subscription after
repeated failures, so an outbound send error has to be logged and swallowed.
These tests send nothing: the Graph client is replaced with a raising stub.
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import whatsapp as wa_router
from app.services.whatsapp import WhatsAppError, _otp_template_payload
import app.config as cfg
from tests.conftest import engine  # noqa: F401  (binds the shared test DB)

client = TestClient(app)


def _signed(payload: dict):
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}


def _inbound_text(from_number="18765550123"):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"changes": [{"value": {
            "contacts": [{"wa_id": from_number}],
            "messages": [{"from": from_number, "id": "wamid.TEST",
                          "type": "text", "text": {"body": "hello"}}],
        }}]}],
    }


@pytest.fixture
def exploding_send(monkeypatch):
    async def _boom(to_number, body):
        raise WhatsAppError(
            400,
            {"error": {"message": "Unsupported post request.", "code": 100,
                       "error_subcode": 33, "fbtrace_id": "TEST"}},
            "https://graph.facebook.com/v20.0/BAD_ID/messages",
        )
    monkeypatch.setattr(wa_router.wa, "send_text", _boom)
    return _boom


def test_send_failure_is_acknowledged_not_500(exploding_send):
    raw, headers = _signed(_inbound_text())
    r = client.post("/whatsapp/webhook", content=raw, headers=headers)
    assert r.status_code == 200, "Meta would retry and eventually disable the webhook"
    assert r.json() == {"status": "ok"}


def test_unexpected_error_is_also_acknowledged(monkeypatch):
    async def _boom(*a, **k):
        raise RuntimeError("something unrelated broke")
    monkeypatch.setattr(wa_router, "_handle_message", _boom)

    raw, headers = _signed(_inbound_text())
    r = client.post("/whatsapp/webhook", content=raw, headers=headers)
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_whatsapp_error_exposes_graph_details():
    e = WhatsAppError(
        400,
        {"error": {"message": "Unsupported post request.", "code": 100,
                   "error_subcode": 33,
                   "error_data": {"details": "bad phone number id"}}},
        "https://graph.facebook.com/v20.0/BAD/messages",
    )
    assert e.code == 100 and e.subcode == 33
    assert "Unsupported post request." in str(e)
    assert "bad phone number id" in str(e)


def test_otp_template_payload_matches_the_approved_template():
    """Authentication-category template: body param + copy-code button.

    Renders as: "123456 is your verification code. For your security, do not
    share this code." / "Expires in 15 minutes." / [Copy code]
    """
    cfg.settings.whatsapp_otp_template = "number_verification"
    cfg.settings.whatsapp_otp_template_lang = "en"

    payload = _otp_template_payload("18765550123", "123456", with_button=True)
    assert payload["type"] == "template"
    assert payload["template"]["name"] == APPROVED_TEMPLATE["name"]
    # "en" and "en_US" are distinct templates to Meta; a mismatch is 132001.
    assert payload["template"]["language"] == {"code": "en"}

    comps = payload["template"]["components"]
    assert [c["type"] for c in comps] == ["body", "button"]
    assert comps[0]["parameters"] == [{"type": "text", "text": "123456"}]
    # Authentication templates send the button as sub_type "url" at index "0",
    # carrying the same code that the body does.
    assert comps[1]["sub_type"] == "url"
    assert comps[1]["index"] == "0"
    assert comps[1]["parameters"] == [{"type": "text", "text": "123456"}]


def test_otp_template_payload_without_button():
    """Shape used for utility-category templates that have no button."""
    body_only = _otp_template_payload("18765550123", "123456", with_button=False)
    assert len(body_only["template"]["components"]) == 1


def test_defaults_match_the_deployed_template():
    from app.config import Settings
    d = Settings()
    assert d.whatsapp_otp_template == "number_verification"
    assert d.whatsapp_otp_template_lang == "en"
    assert d.whatsapp_otp_template_copy_code is True


def test_otp_ttl_matches_template_expiry_footer():
    """Template footer says "Expires in 15 minutes" — the code must agree."""
    from app.config import Settings
    assert Settings().otp_ttl_seconds == 15 * 60


# ── Approved template definition, fetched from Graph ──────────────────────
#   GET https://graph.facebook.com/v20.0/26362065543403544
#       ?fields=id,name,language,status,category,components
# Pinned here so the send payload is checked against Meta's real definition
# without a network call. Re-fetch and update this if the template changes.
APPROVED_TEMPLATE = {
    "id": "26362065543403544",
    "name": "number_verification",
    "language": "en",
    "status": "APPROVED",
    "category": "AUTHENTICATION",
    "components": [
        {
            "type": "BODY",
            "text": "*{{1}}* is your verification code. For your security, do not share this code.",
            "add_security_recommendation": True,
        },
        {
            "type": "FOOTER",
            "text": "Expires in 15 minutes.",
            "code_expiration_minutes": 15,
        },
        {
            "type": "BUTTONS",
            "buttons": [{
                "type": "URL",
                "text": "Copy code",
                "url": "https://www.whatsapp.com/otp/code/?otp_type=COPY_CODE"
                       "&code_expiration_minutes=15&code=otp{{1}}",
            }],
        },
    ],
}


def _component(kind):
    return next(c for c in APPROVED_TEMPLATE["components"] if c["type"] == kind)


def test_send_payload_satisfies_the_approved_definition():
    """Our components must line up with what Meta approved, part for part."""
    from app.config import Settings
    cfg.settings.whatsapp_otp_template = APPROVED_TEMPLATE["name"]
    cfg.settings.whatsapp_otp_template_lang = APPROVED_TEMPLATE["language"]

    settings = Settings()
    assert settings.whatsapp_otp_template == APPROVED_TEMPLATE["name"]
    assert settings.whatsapp_otp_template_lang == APPROVED_TEMPLATE["language"]

    payload = _otp_template_payload(
        "18765550123", "123456", with_button=settings.whatsapp_otp_template_copy_code
    )
    comps = payload["template"]["components"]

    # BODY: one {{n}} placeholder -> exactly one text parameter.
    assert _component("BODY")["text"].count("{{") == 1
    body = next(c for c in comps if c["type"] == "body")
    assert body["parameters"] == [{"type": "text", "text": "123456"}]

    # BUTTONS: the copy-code URL interpolates {{1}} and needs its own parameter.
    button_def = _component("BUTTONS")["buttons"][0]
    assert "otp_type=COPY_CODE" in button_def["url"] and "{{1}}" in button_def["url"]
    assert settings.whatsapp_otp_template_copy_code is True, (
        "AUTHENTICATION templates carry a copy-code button; omitting it is a param mismatch"
    )
    button = next(c for c in comps if c["type"] == "button")
    assert button["sub_type"] == "url" and button["index"] == "0"
    assert button["parameters"] == [{"type": "text", "text": "123456"}]


def test_ttl_matches_the_templates_code_expiration():
    """OTP lifetime must equal the template's advertised expiry, not just its footer text."""
    from app.config import Settings
    minutes = _component("FOOTER")["code_expiration_minutes"]
    assert Settings().otp_ttl_seconds == minutes * 60


def test_template_is_approved_and_authentication_category():
    assert APPROVED_TEMPLATE["status"] == "APPROVED"
    assert APPROVED_TEMPLATE["category"] == "AUTHENTICATION"
