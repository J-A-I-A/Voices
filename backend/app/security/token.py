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


def decode_access_token(token: str) -> dict:
    """Decode and verify an access token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])

