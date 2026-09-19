"""OTP issuance: generation, storage, expiry, attempt caps, resend cooldown."""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy.orm import Session

from ..config import settings
from ..models.verification_code import VerificationCode
from ..models.user import User
from ..security.hashing import generate_otp, hash_otp, verify_otp


class OTPError(Exception):
    pass


class CooldownActive(OTPError):
    pass


def issue_otp(db: Session, user: User, phone: str) -> str:
    """Create a new VerificationCode. Enforces the per-phone resend cooldown.

    Returns the *plaintext* code (only here, to send over WhatsApp); only the
    hash is persisted.
    """
    now = _dt.datetime.now(_dt.timezone.utc)
    # Cooldown: most recent unconsumed code for this phone within the window.
    recent = (
        db.query(VerificationCode)
        .filter(VerificationCode.phone == phone, VerificationCode.consumed.is_(False))
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if recent and recent.created_at.replace(tzinfo=_dt.timezone.utc) > now - _dt.timedelta(
        seconds=settings.otp_resend_cooldown_seconds
    ):
        wait = int(
            (
                recent.created_at.replace(tzinfo=_dt.timezone.utc)
                + _dt.timedelta(seconds=settings.otp_resend_cooldown_seconds)
                - now
            ).total_seconds()
        )
        raise CooldownActive(f"Please wait {wait}s before requesting a new code.")

    code = generate_otp(6)
    vc = VerificationCode(
        user_id=user.id,
        phone=phone,
        code_hash=hash_otp(code),
        expires_at=now + _dt.timedelta(seconds=settings.otp_ttl_seconds),
        attempts=0,
        consumed=False,
    )
    db.add(vc)
    db.commit()
    return code


def verify_code(db: Session, phone: str, code: str) -> Optional[VerificationCode]:
    """Verify an OTP. Returns the code record on success, None on wrong code.

    Raises OTPError if expired or max attempts reached.
    """
    vc = (
        db.query(VerificationCode)
        .filter(VerificationCode.phone == phone, VerificationCode.consumed.is_(False))
        .order_by(VerificationCode.created_at.desc())
        .first()
    )
    if not vc:
        return None
    now = _dt.datetime.now(_dt.timezone.utc)
    if vc.expires_at.replace(tzinfo=_dt.timezone.utc) < now:
        raise OTPError("This code has expired. Please request a new one.")
    if vc.attempts >= settings.otp_max_attempts:
        raise OTPError("Too many incorrect attempts. Please request a new code.")
    if not verify_otp(code, vc.code_hash):
        vc.attempts += 1
        db.commit()
        return None
    vc.consumed = True
    db.commit()
    return vc

