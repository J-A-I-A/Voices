"""Meta WhatsApp Cloud API client (send messages + fetch media bytes)."""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from ..config import settings

logger = logging.getLogger("carib.whatsapp")

GRAPH_BASE = "https://graph.facebook.com"
API_VERSION = "v20.0"

# Graph error codes we react to specifically.
# https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
ERR_REENGAGEMENT = 131047       # outside the 24h window -> template required
ERR_TEMPLATE_MISSING = 132001   # template name/language not found
ERR_TEMPLATE_PARAMS = {132000, 132012}  # component/param count or format mismatch
ERR_TEMPLATE_UNUSABLE = {132015, 132016}  # paused / disabled

# Graph's messages are terse and the same code covers several misconfigurations.
# These hints name the thing to actually go and check.
_ERROR_HINTS: dict[int, str] = {
    100: (
        "The access token is not authorized to send as this phone number id. "
        "Usually WHATSAPP_TOKEN belongs to a different Meta app than the one that "
        "owns WHATSAPP_PHONE_NUMBER_ID, or its whatsapp_business_messaging "
        "permission is not bound to that WhatsApp Business Account. "
        "Run `python -m app.check_whatsapp` to compare the credentials."
    ),
    190: "The access token is invalid or expired — generate a new one.",
    131030: (
        "Recipient is not in the test number's allow-list. Test numbers may only "
        "message up to 5 numbers registered in the Meta app dashboard."
    ),
    131047: (
        "Outside the 24-hour customer service window — free-form text is not "
        "allowed here, send an approved template instead."
    ),
    131026: "The recipient number is not a WhatsApp user or cannot receive messages.",
    132001: (
        "Template name/language not found. Name and language must match the "
        "approved template exactly ('en' and 'en_US' are different templates)."
    ),
    133010: "Phone number is not registered for the Cloud API.",
}


class WhatsAppError(RuntimeError):
    """A Graph API call failed, carrying Meta's own error details.

    httpx's raise_for_status() discards the response body, but Meta puts the
    actual reason there (bad phone number id, template mismatch, expired
    token...). Keeping it is the difference between a debuggable log line and
    a bare '400 Bad Request'.
    """

    def __init__(self, status: int, payload: dict[str, Any] | None, url: str):
        err = (payload or {}).get("error") or {}
        self.status = status
        self.url = url
        self.code: Optional[int] = err.get("code")
        self.subcode: Optional[int] = err.get("error_subcode")
        self.message: str = err.get("message") or f"HTTP {status}"
        self.details: str = (err.get("error_data") or {}).get("details") or ""
        self.fbtrace_id: str = err.get("fbtrace_id") or ""
        self.hint: str = _ERROR_HINTS.get(self.code or -1, "")
        super().__init__(
            f"WhatsApp API {status} (code={self.code} subcode={self.subcode}): "
            f"{self.message}"
            f"{' — ' + self.details if self.details else ''}"
            f"{' | HINT: ' + self.hint if self.hint else ''}"
            f"{' | fbtrace_id=' + self.fbtrace_id if self.fbtrace_id else ''}"
        )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }


def _messages_url() -> str:
    return f"{GRAPH_BASE}/{API_VERSION}/{settings.whatsapp_phone_number_id}/messages"


async def _post_message(payload: dict) -> dict:
    """POST to /messages, raising WhatsAppError with Meta's details on failure."""
    url = _messages_url()
    async with httpx.AsyncClient(timeout=30) as cx:
        r = await cx.post(url, headers=_headers(), json=payload)
        if r.is_success:
            return r.json()
        try:
            body = r.json()
        except Exception:
            body = {"error": {"message": r.text[:500]}}
        raise WhatsAppError(r.status_code, body, url)


async def send_text(to_number: str, body: str) -> dict:
    """Send a free-form text message. `to_number` is digits-only (no '+').

    Note: Meta only delivers free-form messages inside the 24-hour customer
    service window (i.e. after the user has messaged the agent). Outside it,
    this fails with code 131047 and a template must be used instead.
    """
    return await _post_message(
        {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": body, "preview_url": False},
        }
    )


def _otp_template_payload(to_number: str, code: str, *, with_button: bool) -> dict:
    """Build the verification-template send.

    The template takes the code as its single body parameter — the Carib
    Voices body is "*{{1}}* is your verification code." Templates created in
    Meta's authentication category additionally carry a copy-code / one-tap
    button that must be sent the same code, or Graph rejects the send for a
    parameter mismatch; `with_button` covers that case.
    """
    components: list[dict[str, Any]] = [
        {"type": "body", "parameters": [{"type": "text", "text": code}]}
    ]
    if with_button:
        components.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": code}],
            }
        )
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "template",
        "template": {
            "name": settings.whatsapp_otp_template,
            "language": {"code": settings.whatsapp_otp_template_lang},
            "components": components,
        },
    }


def _otp_text(code: str) -> str:
    return (
        f"Your Carib Voices verification code is {code}. "
        f"It expires in {settings.otp_ttl_seconds // 60} minutes. "
        f"Do not share this code with anyone."
    )


async def send_otp(to_number: str, code: str) -> dict:
    """Deliver a verification code.

    Prefers the approved authentication template, because a user verifying
    their number has usually never messaged the agent, so no 24-hour customer
    service window is open and a free-form text would be rejected (131047).

    Falls back to plain text when the template is unavailable, which still
    works for anyone already inside the window.
    """
    if not code:
        raise ValueError("send_otp requires a code")

    if settings.whatsapp_use_otp_template and settings.whatsapp_otp_template:
        want_button = settings.whatsapp_otp_template_copy_code
        try:
            return await _post_message(
                _otp_template_payload(to_number, code, with_button=want_button)
            )
        except WhatsAppError as e:
            if e.code in ERR_TEMPLATE_PARAMS:
                # Our idea of the template's components disagrees with Meta's.
                # Retry with the opposite shape before giving up, so a template
                # edit (adding or removing a copy-code button) can't silently
                # break verification.
                logger.info(
                    "OTP template '%s' rejected components with_button=%s (code=%s); "
                    "retrying with with_button=%s.",
                    settings.whatsapp_otp_template, want_button, e.code, not want_button,
                )
                try:
                    return await _post_message(
                        _otp_template_payload(to_number, code, with_button=not want_button)
                    )
                except WhatsAppError as e2:
                    logger.error(
                        "OTP template send failed both with and without the button "
                        "component: %s. Check WHATSAPP_OTP_TEMPLATE_COPY_CODE.", e2,
                    )
                    raise
            if e.code == ERR_TEMPLATE_MISSING or e.code in ERR_TEMPLATE_UNUSABLE:
                logger.error(
                    "OTP template '%s' (%s) is missing, paused or disabled (code=%s): %s. "
                    "Falling back to plain text, which only reaches users inside the "
                    "24-hour customer service window.",
                    settings.whatsapp_otp_template,
                    settings.whatsapp_otp_template_lang,
                    e.code,
                    e.message,
                )
                return await send_text(to_number, _otp_text(code))
            raise

    return await send_text(to_number, _otp_text(code))


async def fetch_media_bytes(media_id: str) -> tuple[bytes, str]:
    """Resolve a media id to a URL then download the bytes. Returns (bytes, mime_type)."""
    async with httpx.AsyncClient(timeout=60, headers=_headers()) as cx:
        meta = await cx.get(f"{GRAPH_BASE}/{API_VERSION}/{media_id}")
        meta.raise_for_status()
        meta_j = meta.json()
        url = meta_j["url"]
        mime = meta_j.get("mime_type", "audio/ogg")
        dl = await cx.get(url)
        dl.raise_for_status()
        return dl.content, mime


def agent_wame_link(starter_text: Optional[str] = None) -> str:
    """wa.me deep link to the agent's number, with optional prefilled text."""
    base = f"https://wa.me/{settings.agent_whatsapp_number}"
    if starter_text:
        import urllib.parse
        return f"{base}?text={urllib.parse.quote(starter_text)}"
    return base
