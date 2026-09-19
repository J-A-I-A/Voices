"""Hashing helpers: OTPs (SHA-256 with pepper) and passwords (bcrypt)."""
from __future__ import annotations

import hashlib
import hmac
import secrets

from passlib.context import CryptContext

from ..config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _pepper() -> bytes:
    return settings.jwt_secret.encode("utf-8")


def hash_otp(code: str) -> str:
    """Hash an OTP for at-rest storage. Uses HMAC-SHA256 with the JWT secret as pepper."""
    return hmac.new(_pepper(), code.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp(code: str, code_hash: str) -> bool:
    expected = hash_otp(code)
    return hmac.compare_digest(expected, code_hash)


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


def generate_otp(length: int = 6) -> str:
    """Generate a 0-padded numeric OTP of the given length."""
    max_val = 10 ** length - 1
    return f"{secrets.randbelow(max_val + 1):0{length}d}"

