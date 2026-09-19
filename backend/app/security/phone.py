"""Jamaica-only WhatsApp number validation and E.164 normalization.

Jamaica is on the North American Numbering Plan (country code +1) with area
codes 876 and 658. We accept flexible input ("876 555 1234", "+1 876 555 1234",
"(876)555-1234", "18765551234") and normalize to E.164: "+1876XXXXXXX" or
"+1658XXXXXXX". Any other area code or country is rejected.
"""
from __future__ import annotations

import re

# Keep digits only.
_NON_DIGITS = re.compile(r"\D+")

JAMAICA_AREA_CODES = {"876", "658"}
JAMAICA_E164_PATTERN = re.compile(r"^\+1(?:876|658)\d{7}$")


class InvalidJamaicanNumberError(ValueError):
    """Raised when a number is not a valid Jamaican (+1 / 876|658) number."""


def _digits(raw: str) -> str:
    if raw is None:
        raise InvalidJamaicanNumberError("Phone number is required.")
    return _NON_DIGITS.sub("", raw)


def normalize_jamaican(raw: str) -> str:
    """Normalize an arbitrary input string to a Jamaican E.164 number.

    Returns "+1876XXXXXXX" or "+1658XXXXXXX".
    Raises InvalidJamaicanNumberError if the number is not Jamaican.
    """
    digits = _digits(raw)
    if not digits:
        raise InvalidJamaicanNumberError("Phone number is required.")

    # Handle a domestic 10-digit NANP number: 1ACXXXXXXXXX -> remove leading 1
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        area, rest = digits[:3], digits[3:]
        if area in JAMAICA_AREA_CODES and len(rest) == 7 and digits[0] not in ("0", "1"):
            return f"+1{digits}"
        raise InvalidJamaicanNumberError(
            "Only Jamaican WhatsApp numbers (876 or 658) can register at this time."
        )
    if len(digits) == 11 and digits.startswith("1"):
        # 1 + 876/658 + 7 digits
        area, rest = digits[1:4], digits[4:]
        if area in JAMAICA_AREA_CODES and len(rest) == 7:
            return f"+{digits}"
    raise InvalidJamaicanNumberError(
        "Only Jamaican WhatsApp numbers (876 or 658) can register at this time."
    )


def is_jamaican_e164(value: str) -> bool:
    """Return True if value is already normalized Jamaican E.164."""
    return bool(value and JAMAICA_E164_PATTERN.match(value))
