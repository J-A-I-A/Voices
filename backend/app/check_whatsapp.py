"""WhatsApp credential coherence check.

    docker compose exec backend python -m app.check_whatsapp

Verifies that WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_APP_SECRET
and the OTP template all belong together. Graph reports most mismatches as a
bare "(#100) Authorization Error" on send, which says nothing about which of
the four is wrong — this pinpoints it.

Read-only: it sends no messages. Secrets are never printed.
"""
from __future__ import annotations

import sys

import httpx

from .config import settings

GRAPH = "https://graph.facebook.com/v20.0"

OK, WARN, BAD = "  OK  ", " WARN ", " FAIL "


def _line(tag: str, text: str) -> None:
    print(f"[{tag}] {text}")


def _get(path: str, token: str, **params) -> tuple[int, dict]:
    try:
        r = httpx.get(f"{GRAPH}/{path}", params=params,
                      headers={"Authorization": f"Bearer {token}"}, timeout=30)
        return r.status_code, (r.json() if r.content else {})
    except Exception as e:  # network, DNS, proxy...
        return 0, {"error": {"message": str(e)}}


def main() -> int:
    problems: list[str] = []

    token = settings.whatsapp_token
    phone_id = settings.whatsapp_phone_number_id
    if not token:
        _line(BAD, "WHATSAPP_TOKEN is empty.")
        return 1
    if not phone_id:
        _line(BAD, "WHATSAPP_PHONE_NUMBER_ID is empty.")
        return 1
    if not phone_id.isdigit():
        _line(BAD, f"WHATSAPP_PHONE_NUMBER_ID={phone_id!r} is not all digits — "
                   "every send will fail with HTTP 400.")
        problems.append("phone number id")

    # ── 1. Token identity and scopes ────────────────────────────────────
    status, body = _get("debug_token", token, input_token=token)
    app_id = None
    if status == 200 and "data" in body:
        d = body["data"]
        app_id = d.get("app_id")
        scopes = d.get("scopes") or []
        _line(OK if d.get("is_valid") else BAD,
              f"Token: type={d.get('type')} app={d.get('application')!r} app_id={app_id} "
              f"valid={d.get('is_valid')} expires={'never' if d.get('expires_at') == 0 else d.get('expires_at')}")
        if "whatsapp_business_messaging" in scopes:
            _line(OK, "Token has whatsapp_business_messaging.")
        else:
            _line(BAD, f"Token is MISSING whatsapp_business_messaging (scopes: {scopes}).")
            problems.append("token scope")
    else:
        _line(WARN, f"Could not introspect the token (HTTP {status}); continuing.")

    # ── 2. Phone number is readable and connected ───────────────────────
    status, body = _get(phone_id, token,
                        fields="id,display_phone_number,verified_name,status,platform_type,account_mode")
    if status == 200:
        _line(OK, f"Phone number {phone_id}: {body.get('display_phone_number')} "
                  f"({body.get('verified_name')}) status={body.get('status')} "
                  f"platform={body.get('platform_type')} mode={body.get('account_mode')}")
        if str(body.get("verified_name", "")).lower() == "test number":
            _line(WARN, "This is a Meta TEST number: it can only message up to 5 "
                        "recipient numbers registered in the app dashboard.")
    else:
        _line(BAD, f"Cannot read phone number {phone_id}: {body.get('error', {}).get('message')}")
        problems.append("phone number id")

    # ── 3. App secret belongs to the same app as the token ──────────────
    if app_id and settings.whatsapp_app_secret:
        r = httpx.get(f"{GRAPH}/{app_id}", params={
            "fields": "id,name",
            "access_token": f"{app_id}|{settings.whatsapp_app_secret}",
        }, timeout=30)
        if r.status_code == 200:
            _line(OK, f"WHATSAPP_APP_SECRET belongs to the same app as the token ({app_id}).")
        else:
            _line(BAD, "WHATSAPP_APP_SECRET does NOT belong to the token's app "
                       f"({app_id}). The token and the secret come from different "
                       "Meta apps — that mismatch also breaks webhook signature "
                       "verification if the secret is the wrong one.")
            problems.append("app secret / token app mismatch")
    elif not settings.whatsapp_app_secret:
        _line(WARN, "WHATSAPP_APP_SECRET is empty — webhook signatures are not verified.")

    # ── 4. OTP template matches what is configured ──────────────────────
    if settings.whatsapp_use_otp_template:
        tid = settings.whatsapp_otp_template_id
        if tid:
            status, body = _get(tid, token, fields="id,name,language,status,category,components")
            if status == 200:
                same_name = body.get("name") == settings.whatsapp_otp_template
                same_lang = body.get("language") == settings.whatsapp_otp_template_lang
                _line(OK if same_name and same_lang else BAD,
                      f"Template {tid}: name={body.get('name')!r} language={body.get('language')!r} "
                      f"status={body.get('status')} category={body.get('category')}")
                if not same_name:
                    _line(BAD, f"  WHATSAPP_OTP_TEMPLATE={settings.whatsapp_otp_template!r} does not match.")
                    problems.append("template name")
                if not same_lang:
                    _line(BAD, f"  WHATSAPP_OTP_TEMPLATE_LANG={settings.whatsapp_otp_template_lang!r} "
                               "does not match ('en' and 'en_US' are different templates).")
                    problems.append("template language")

                comps = {c.get("type"): c for c in body.get("components", [])}
                has_buttons = "BUTTONS" in comps
                if has_buttons != settings.whatsapp_otp_template_copy_code:
                    _line(BAD, f"  WHATSAPP_OTP_TEMPLATE_COPY_CODE={settings.whatsapp_otp_template_copy_code} "
                               f"but the template {'HAS' if has_buttons else 'has NO'} button component.")
                    problems.append("template copy-code button")
                else:
                    _line(OK, f"  Button component expectation matches (copy_code={has_buttons}).")

                footer = comps.get("FOOTER") or {}
                mins = footer.get("code_expiration_minutes")
                if mins:
                    if mins * 60 == settings.otp_ttl_seconds:
                        _line(OK, f"  OTP_TTL_SECONDS matches the template expiry ({mins} minutes).")
                    else:
                        _line(BAD, f"  Template expires codes after {mins} minutes but "
                                   f"OTP_TTL_SECONDS={settings.otp_ttl_seconds} "
                                   f"({settings.otp_ttl_seconds // 60} minutes).")
                        problems.append("otp ttl vs template expiry")
            else:
                _line(BAD, f"Cannot read template {tid}: {body.get('error', {}).get('message')}")
                problems.append("template")
        else:
            _line(WARN, "WHATSAPP_OTP_TEMPLATE_ID not set — skipping template checks.")

    print()
    if problems:
        _line(BAD, "Problems found: " + ", ".join(dict.fromkeys(problems)))
        return 1
    _line(OK, "All WhatsApp credentials are coherent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
