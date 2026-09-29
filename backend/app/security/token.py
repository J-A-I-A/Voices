"""JWT access tokens (HS256)."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from jose import JWTError, jwt

from ..config import settings


def create_access_token(subject: str | int, *, extra: Optional[dict] = None) -> str:
    now = _dt.datetime.now(_dt.timezone.utc)
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": now + _dt.timedelta(minutes=settings.access_token_ttl_minutes),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_email_verify_token(user_id: str, email: str) -> str:
    """Signed link token for confirming an email address.

    Carries the address it was issued for, so a token stops working if the
    account's email no longer matches. type="email_verify" keeps it from ever
    passing as an access token (get_current_user requires type="access").
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": now,
        "exp": now + _dt.timedelta(hours=settings.email_verification_ttl_hours),
        "type": "email_verify",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_email_verify_token(token: str) -> dict:
    """Decode an email verification token. Raises JWTError if invalid, expired or the wrong type."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    if payload.get("type") != "email_verify":
        raise JWTError("not an email verification token")
    return payload


def decode_access_token(token: str) -> dict:
    """Decode and verify an access token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])

