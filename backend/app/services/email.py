"""Transactional email via Resend's HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""
from __future__ import annotations

import html
import logging
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger("carib.email")

RESEND_URL = "https://api.resend.com/emails"


class EmailError(Exception):
    pass


async def send_email(to: str, subject: str, text: str, html_body: str, *, dev_hint: Optional[str] = None) -> None:
    if not settings.resend_api_key:
        # Local dev: no Resend key. Log instead so the flow is still testable.
        logger.warning("RESEND_API_KEY not set — not sending %r to %s. %s", subject, to, dev_hint or "")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.email_from,
                    "to": [to],
                    "subject": subject,
                    "text": text,
                    "html": html_body,
                },
            )
    except httpx.HTTPError as e:
        raise EmailError(f"Resend request failed: {e}") from e
    if r.status_code >= 300:
        raise EmailError(f"Resend returned {r.status_code}: {r.text[:300]}")


async def send_verification_email(to: str, first_name: str, link: str) -> None:
    name = first_name or "there"
    hours = settings.email_verification_ttl_hours
    subject = "Confirm your email for Carib Voices"
    text = (
        f"Hi {name},\n\n"
        f"Please confirm your email address to finish setting up your Carib Voices account:\n\n"
        f"{link}\n\n"
        f"This link expires in {hours} hours. If you didn't sign up, you can ignore this email.\n\n"
        f"— Carib Voices"
    )
    safe_link = html.escape(link, quote=True)
    html_body = f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#f6f4ef;font-family:Poppins,Arial,sans-serif;color:#171717">
  <table role="presentation" width="100%" style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e4e0d6;border-radius:20px">
    <tr><td style="padding:32px">
      <p style="margin:0 0 20px;font-size:22px;font-weight:800">Carib<span style="color:#009b3a">Voices</span></p>
      <p style="margin:0 0 12px;font-size:16px">Hi {html.escape(name)},</p>
      <p style="margin:0 0 24px;font-size:15px;line-height:1.5;color:#4a4a4a">
        Please confirm your email address to finish setting up your account.
      </p>
      <a href="{safe_link}" style="display:inline-block;padding:14px 28px;background:#009b3a;color:#ffffff;text-decoration:none;border-radius:999px;font-weight:600;font-size:15px">
        Confirm email
      </a>
      <p style="margin:24px 0 0;font-size:13px;line-height:1.5;color:#67625a">
        This link expires in {hours} hours. If the button doesn't work, paste this into your browser:<br>
        <a href="{safe_link}" style="color:#009b3a;word-break:break-all">{safe_link}</a>
      </p>
      <p style="margin:16px 0 0;font-size:13px;color:#67625a">If you didn't sign up, you can ignore this email.</p>
    </td></tr>
  </table>
</body></html>"""
    await send_email(to, subject, text, html_body, dev_hint=f"Verification link: {link}")
