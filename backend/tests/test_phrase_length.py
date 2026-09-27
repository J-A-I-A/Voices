"""Phrase length bands: short <10s, medium 10-20s, long 20-35s.

Word thresholds are derived from those seconds and the speaking rate, so the
tests assert the relationship rather than hard-coded word counts — changing
PHRASE_WORDS_PER_MINUTE must move every band together.
"""
import datetime as _dt
import io

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.models.phrase import PHRASE_TEXT_MAX_CHARS, Phrase
from app.models.user import AuthProvider, User
from app.security.token import create_access_token
from app.services.phrase_length import (
    PhraseLength, band_for_text, band_for_words, count_words, estimated_seconds,
    exceeds_maximum, thresholds, word_range_for,
)
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)


def _words(n: int, word: str = "mi") -> str:
    return " ".join([word] * n) + "."


@pytest.fixture
def admin_headers():
    s = Session()
    try:
        u = User(first_name="Len", last_name="Admin", date_of_birth=_dt.date(1985, 2, 2),
                 email="length-admin@example.com", auth_provider=AuthProvider.email,
                 password_hash="x", is_admin=True)
        s.add(u)
        s.commit()
        uid = u.id
    finally:
        s.close()
    return {"Authorization": "Bearer " + create_access_token(uid)}


# ─── Word counting ──────────────────────────────────────────────────────
def test_counts_words_ignoring_punctuation():
    assert count_words("Wah gwaan, Jamaica!") == 3


def test_contractions_count_as_one_word():
    assert count_words("Mi nuh know if yuh don't come") == 7


def test_empty_text_is_zero():
    assert count_words("") == 0 and count_words(None) == 0


# ─── Bands follow the seconds, not magic numbers ────────────────────────
def test_thresholds_match_the_configured_seconds():
    t = thresholds()
    assert estimated_seconds(t.short_max_words) <= t.short_max_seconds
    assert estimated_seconds(t.medium_max_words) <= t.medium_max_seconds
    assert estimated_seconds(t.long_max_words) <= t.long_max_seconds
    # One word more must spill past the bound.
    assert estimated_seconds(t.short_max_words + 1) > t.short_max_seconds
    assert estimated_seconds(t.medium_max_words + 1) > t.medium_max_seconds
    assert estimated_seconds(t.long_max_words + 1) > t.long_max_seconds


def test_band_boundaries():
    t = thresholds()
    assert band_for_words(1) is PhraseLength.short
    assert band_for_words(t.short_max_words) is PhraseLength.short
    assert band_for_words(t.short_max_words + 1) is PhraseLength.medium
    assert band_for_words(t.medium_max_words) is PhraseLength.medium
    assert band_for_words(t.medium_max_words + 1) is PhraseLength.long
    assert band_for_words(t.long_max_words) is PhraseLength.long


def test_beyond_the_long_bound_is_rejected():
    t = thresholds()
    assert not exceeds_maximum(t.long_max_words)
    assert exceeds_maximum(t.long_max_words + 1)


def test_word_ranges_are_contiguous_and_non_overlapping():
    s_lo, s_hi = word_range_for(PhraseLength.short)
    m_lo, m_hi = word_range_for(PhraseLength.medium)
    l_lo, l_hi = word_range_for(PhraseLength.long)
    assert s_lo == 1
    assert m_lo == s_hi + 1
    assert l_lo == m_hi + 1
    assert l_hi == thresholds().long_max_words


def test_changing_the_speaking_rate_moves_every_band(monkeypatch):
    """The bands are defined in seconds; words are only a derived view."""
    fast = thresholds()
    monkeypatch.setattr(settings, "phrase_words_per_minute", settings.phrase_words_per_minute // 2)
    slow = thresholds()
    assert slow.short_max_words < fast.short_max_words
    assert slow.medium_max_words < fast.medium_max_words
    assert slow.long_max_words < fast.long_max_words
    # The seconds they represent are unchanged.
    assert slow.short_max_seconds == fast.short_max_seconds


def test_band_for_text_matches_band_for_words():
    text = _words(30)
    assert band_for_text(text) is band_for_words(count_words(text))


# ─── API ────────────────────────────────────────────────────────────────
def test_created_phrase_reports_its_band(admin_headers):
    t = thresholds()
    r = client.post("/admin/phrases", json={"text": _words(t.short_max_words - 1)},
                    headers=admin_headers)
    assert r.status_code == 201
    d = r.json()
    assert d["length"] == "short"
    assert d["word_count"] == t.short_max_words - 1
    assert d["estimated_seconds"] <= t.short_max_seconds


def test_medium_and_long_phrases_are_classified(admin_headers):
    t = thresholds()
    med = client.post("/admin/phrases", json={"text": _words(t.short_max_words + 2)},
                      headers=admin_headers).json()
    lng = client.post("/admin/phrases", json={"text": _words(t.medium_max_words + 2)},
                      headers=admin_headers).json()
    assert med["length"] == "medium"
    assert lng["length"] == "long"


def test_over_long_phrase_is_refused(admin_headers):
    t = thresholds()
    r = client.post("/admin/phrases", json={"text": _words(t.long_max_words + 10)},
                    headers=admin_headers)
    assert r.status_code == 422
    assert f"{t.long_max_seconds}s maximum" in r.json()["detail"]


def test_editing_text_updates_the_band(admin_headers):
    t = thresholds()
    pid = client.post("/admin/phrases", json={"text": _words(3)}, headers=admin_headers).json()["id"]
    updated = client.patch(f"/admin/phrases/{pid}",
                           json={"text": _words(t.medium_max_words + 3)},
                           headers=admin_headers).json()
    assert updated["length"] == "long"

    s = Session()
    try:
        # The cached count must not drift from the text.
        p = s.get(Phrase, pid)
        assert p.word_count == count_words(p.text)
    finally:
        s.close()


def test_editing_to_an_over_long_phrase_is_refused(admin_headers):
    t = thresholds()
    pid = client.post("/admin/phrases", json={"text": _words(3)}, headers=admin_headers).json()["id"]
    r = client.patch(f"/admin/phrases/{pid}", json={"text": _words(t.long_max_words + 5)},
                     headers=admin_headers)
    assert r.status_code == 422


def test_filter_by_band(admin_headers):
    t = thresholds()
    client.post("/admin/phrases", json={"text": _words(2)}, headers=admin_headers)
    client.post("/admin/phrases", json={"text": _words(t.short_max_words + 4)}, headers=admin_headers)

    short = client.get("/admin/phrases?length=short", headers=admin_headers).json()
    medium = client.get("/admin/phrases?length=medium", headers=admin_headers).json()
    assert all(p["length"] == "short" for p in short)
    assert all(p["length"] == "medium" for p in medium)
    assert medium, "the medium phrase was not returned"


def test_invalid_band_is_rejected(admin_headers):
    assert client.get("/admin/phrases?length=enormous", headers=admin_headers).status_code == 422


def test_lengths_endpoint_summarises_the_bank(admin_headers):
    d = client.get("/admin/phrases/lengths", headers=admin_headers).json()
    assert d["words_per_minute"] == settings.phrase_words_per_minute
    bands = {b["band"]: b for b in d["bands"]}
    assert set(bands) == {"short", "medium", "long"}
    assert bands["short"]["max_seconds"] == settings.phrase_short_max_seconds
    assert bands["long"]["max_seconds"] == settings.phrase_long_max_seconds


# ─── Import ─────────────────────────────────────────────────────────────
def _xlsx(rows) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_import_reports_the_band_mix(admin_headers):
    t = thresholds()
    data = _xlsx([
        ["Phrase"],
        [_words(4)],
        [_words(t.short_max_words + 3)],
        [_words(t.medium_max_words + 3)],
    ])
    d = client.post("/admin/phrases/import", headers=admin_headers,
                    files={"file": ("p.xlsx", data, "application/vnd.ms-excel")}).json()
    assert d["added"] == 3
    assert d["by_length"] == {"short": 1, "medium": 1, "long": 1}


def test_import_skips_phrases_that_are_too_long(admin_headers):
    t = thresholds()
    data = _xlsx([["Phrase"], [_words(5)], [_words(t.long_max_words + 20)]])
    d = client.post("/admin/phrases/import", headers=admin_headers,
                    files={"file": ("p.xlsx", data, "application/vnd.ms-excel")}).json()
    assert d["added"] == 1
    assert any("too long to read in one take" in x for x in d["details"])


# ─── Duration, not storage, is the binding limit ────────────────────────
def test_the_longest_allowed_phrase_fits_in_the_column():
    """A phrase at the word limit must be storable even with long words.

    The text column used to be 500 characters, which could reject a phrase
    that was still inside the 35-second reading limit purely because its
    words were long. The column now follows from the word limit.
    """
    t = thresholds()
    longest = _words(t.long_max_words, word="w" * 20)
    assert not exceeds_maximum(count_words(longest))
    assert len(longest) <= PHRASE_TEXT_MAX_CHARS, (
        f"{len(longest)} characters exceeds the {PHRASE_TEXT_MAX_CHARS}-character column"
    )


def test_long_worded_phrase_at_the_limit_is_accepted(admin_headers):
    t = thresholds()
    text = _words(t.long_max_words, word="extraordinarily")  # 15 chars a word
    r = client.post("/admin/phrases", json={"text": text}, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["length"] == "long"


def test_over_long_phrase_with_long_words_is_refused_on_duration(admin_headers):
    """The rejection must cite the reading time, not the character count."""
    t = thresholds()
    text = _words(t.long_max_words + 5, word="extraordinarily")
    r = client.post("/admin/phrases", json={"text": text}, headers=admin_headers)
    assert r.status_code == 422
    assert f"{t.long_max_seconds}s maximum" in r.json()["detail"]


def test_import_limits_agree_with_the_column():
    """The parser must not reject something the column could hold."""
    from app.services.phrase_import import MAX_LEN
    assert MAX_LEN == PHRASE_TEXT_MAX_CHARS


def test_import_accepts_a_long_worded_phrase_at_the_limit(admin_headers):
    t = thresholds()
    data = _xlsx([["Phrase"], [_words(t.long_max_words, word="extraordinarily")]])
    d = client.post("/admin/phrases/import", headers=admin_headers,
                    files={"file": ("p.xlsx", data, "application/vnd.ms-excel")}).json()
    assert d["added"] == 1 and d["by_length"]["long"] == 1
