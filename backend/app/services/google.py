"""Google OAuth ID token verification (used for Google sign-in/up).

We verify the OIDC ID token with Google's public keys and check the audience
matches our client id. This avoids a token-exchange round-trip and is exactly
what Auth.js on the portal also does client-side.
"""
from __future__ import annotations

from typing import Optional

import httpx
from jose import jwt

from ..config import settings

_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleTokenError(Exception):
    pass


async def verify_id_token(id_token: str) -> dict:
    """Verify a Google OIDC id_token and return its claims."""
    if not settings.google_client_id:
        raise GoogleTokenError("Google sign-in is not configured on the backend.")

    # Grab the unverified header to find the key id.
    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except Exception as e:
        raise GoogleTokenError(f"Malformed id token: {e}") from e

    kid = unverified_header.get("kid")
    async with httpx.AsyncClient(timeout=15) as cx:
        r = await cx.get(_GOOGLE_CERTS_URL)
        r.raise_for_status()
        jwks = r.json()
    keys = jwks.get("keys", [])
    key = next((k for k in keys if k.get("kid") == kid), None)
    if key is None:
        raise GoogleTokenError("Signing key not found in Google JWKS.")

    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.google_client_id,
            issuer="https://accounts.google.com",
        )
    except Exception as e:
        raise GoogleTokenError(f"Invalid id token: {e}") from e
    return claims


def claims_to_names(claims: dict) -> tuple[str | None, str | None]:
    """Extract (given_name, family_name) from Google claims, if present."""
    given = claims.get("given_name") or claims.get("given_name")
    family = claims.get("family_name")
    return given, family

