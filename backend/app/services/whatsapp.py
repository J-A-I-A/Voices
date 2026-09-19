"""Meta WhatsApp Cloud API client (send messages + fetch media bytes)."""
from __future__ import annotations

from typing import Optional

import httpx

from ..config import settings

GRAPH_BASE = "https://graph.facebook.com"
API_VERSION = "v20.0"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }


async def send_text(to_number: str, body: str) -> dict:
    """Send a text message. `to_number` is digits-only (no '+')."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": body, "preview_url": False},
    }
    async with httpx.AsyncClient(timeout=30) as cx:
        r = await cx.post(
            f"{GRAPH_BASE}/{API_VERSION}/{settings.whatsapp_phone_number_id}/messages",
            headers=_headers(),
            json=payload,
        )
        r.raise_for_status()
        return r.json()


async def send_otp(to_number: str, code: str) -> dict:
    body = (
        f"Your Carib Voices verification code is {code}. "
        f"It expires in {settings.otp_ttl_seconds // 60} minutes. "
        f"Do not share this code with anyone."
    )
    return await send_text(to_number, code and body)


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

