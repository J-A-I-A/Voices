"""Tests for pure security logic (no DB/network)."""
import datetime as _dt

import pytest

from app.security.phone import normalize_jamaican, is_jamaican_e164, InvalidJamaicanNumberError
from app.security.age import age_from_dob, is_at_least_18
from app.security.hashing import generate_otp, hash_otp, verify_otp
from app.services.wer import normalize, compute_wer


@pytest.mark.parametrize('raw,expected', [
    ("8765551234", "+18765551234"),
    ("(876) 555-1234", "+18765551234"),
    ("+1 876 555 1234", "+18765551234"),
    ("18765551234", "+18765551234"),
    ("6585551234", "+16585551234"),
    ("+1 658 555 1234", "+16585551234"),
])
def test_normalize_jamaican_valid(raw, expected):
    assert normalize_jamaican(raw) == expected


@pytest.mark.parametrize('raw', [
    "2125551234",
    "442071234567",
    "876555123",
    "1876555123",
    "0000000000",
    "",
])
def test_normalize_jamaican_invalid(raw):
    with pytest.raises(InvalidJamaicanNumberError):
        normalize_jamaican(raw)


def test_is_jamaican_e164():
    assert is_jamaican_e164("+18765551234")
    assert is_jamaican_e164("+16585551234")
    assert not is_jamaican_e164("18765551234")
    assert not is_jamaican_e164("+12125551234")


def test_age_from_dob_basic():
    today = _dt.date(2024, 1, 1)
    assert age_from_dob(_dt.date(2000, 1, 1), today) == 24
    assert age_from_dob(_dt.date(2006, 1, 2), today) == 17


def test_is_at_least_18():
    today = _dt.date(2024, 1, 1)
    assert is_at_least_18(_dt.date(2006, 1, 1), today) is True
    assert is_at_least_18(_dt.date(2006, 1, 2), today) is False
    assert is_at_least_18(_dt.date(2005, 12, 31), today) is True


def test_otp_hash_roundtrip():
    code = generate_otp(6)
    assert len(code) == 6 and code.isdigit()
    h = hash_otp(code)
    assert h != code
    assert verify_otp(code, h)


def test_normalize_strips_punctuation_and_case():
    assert normalize("Hello, WORLD!") == "hello world"


def test_compute_wer_perfect():
    assert compute_wer("Good morning how are you", "good morning how are you") == 0.0


def test_compute_wer_partial():
    wer = compute_wer("one two three four", "one two five four")
    assert 0.0 < wer < 1.0

# ─── QC WER thresholds / decision ─────────────────────────
def test_wer_decision_boundaries():
    from app.workers.qc import _wer_decision
    # accept at/below 0.30, needs_review in between, reject at/above 0.60
    assert _wer_decision(0.0) == 'accepted'
    assert _wer_decision(0.30) == 'accepted'
    assert _wer_decision(0.31) == 'needs_review'
    assert _wer_decision(0.59) == 'needs_review'
    assert _wer_decision(0.60) == 'rejected'
    assert _wer_decision(0.90) == 'rejected'


def test_compute_wer_alignment():
    # 1 word wrong out of 5 => WER 0.2
    from app.services.wer import compute_wer
    wer = compute_wer('one two three four five', 'one two fish four five')
    assert abs(wer - 0.2) < 1e-6
