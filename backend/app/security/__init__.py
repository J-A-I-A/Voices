"""Security primitives: phone validation, age gate, hashing, JWT."""
from .phone import (
    InvalidJamaicanNumberError,
    normalize_jamaican,
    is_jamaican_e164,
)
from .age import age_from_dob, is_at_least_18
from .hashing import hash_otp, verify_otp, hash_password, verify_password
from .token import create_access_token, decode_access_token

__all__ = [
    "InvalidJamaicanNumberError",
    "normalize_jamaican",
    "is_jamaican_e164",
    "age_from_dob",
    "is_at_least_18",
    "hash_otp",
    "verify_otp",
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
]

