"""Bulk phrase import from spreadsheets, and phrase search."""
import csv
import datetime as _dt
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.phrase import Phrase
from app.models.user import AuthProvider, User
from app.security.token import create_access_token
from app.services.phrase_import import PhraseImportError, parse_phrase_file
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)


@pytest.fixture
def admin_headers():
    s = Session()
    try:
        u = User(first_name="Ad", last_name="Min", date_of_birth=_dt.date(1988, 1, 1),
                 email="import-admin@example.com", auth_provider=AuthProvider.email,
                 password_hash="x", is_admin=True)
        s.add(u)
        s.commit()
        uid = u.id
    finally:
        s.close()
    return {"Authorization": "Bearer " + create_access_token(uid)}


def _xlsx(rows) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(r)
    return buf.getvalue().encode()


def _upload(headers, data: bytes, filename="phrases.xlsx"):
    return client.post("/admin/phrases/import", headers=headers,
                       files={"file": (filename, data,
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


# ─── Parser ─────────────────────────────────────────────────────────────
def test_parses_a_simple_sheet():
    r = parse_phrase_file("p.xlsx", _xlsx([["Wah gwaan Jamaica."], ["Mi deh yah."]]))
    assert [p.text for p in r.phrases] == ["Wah gwaan Jamaica.", "Mi deh yah."]


def test_header_row_is_skipped():
    r = parse_phrase_file("p.xlsx", _xlsx([["Phrase", "Locale"], ["Real phrase here."]]))
    assert [p.text for p in r.phrases] == ["Real phrase here."]


def test_optional_locale_and_active_columns():
    r = parse_phrase_file("p.xlsx", _xlsx([
        ["Active one here.", "en-JM", "yes"],
        ["Inactive one here.", "en-TT", "no"],
        ["Defaults applied here.", "", ""],
    ]))
    assert (r.phrases[0].locale, r.phrases[0].active) == ("en-JM", True)
    assert (r.phrases[1].locale, r.phrases[1].active) == ("en-TT", False)
    assert (r.phrases[2].locale, r.phrases[2].active) == ("en-JM", True)


def test_blank_rows_are_ignored_silently():
    r = parse_phrase_file("p.xlsx", _xlsx([["Good phrase here."], [""], [None], ["Another good one."]]))
    assert len(r.phrases) == 2 and r.skipped == []


def test_too_short_and_too_long_are_reported():
    # Derived from the limit rather than hardcoded, so widening the column
    # does not silently turn this into a no-op.
    from app.services.phrase_import import MAX_LEN
    r = parse_phrase_file("p.xlsx", _xlsx([["ok"], ["x" * (MAX_LEN + 100)],
                                           ["A perfectly fine phrase."]]))
    assert len(r.phrases) == 1
    reasons = " ".join(reason for _, reason in r.skipped)
    assert "too short" in reasons and "too long" in reasons


def test_duplicates_within_the_file_are_dropped():
    """Matching ignores case and collapsed whitespace."""
    r = parse_phrase_file("p.xlsx", _xlsx([
        ["One love, one heart."],
        ["ONE  LOVE,   ONE HEART."],
    ]))
    assert len(r.phrases) == 1
    assert "duplicate" in r.skipped[0][1]


def test_csv_is_accepted():
    r = parse_phrase_file("p.csv", _csv([["Phrase"], ["From a CSV file."]]))
    assert [p.text for p in r.phrases] == ["From a CSV file."]


def test_semicolon_csv_is_accepted():
    data = b"Phrase;Locale\nSemicolon separated here.;en-JM\n"
    r = parse_phrase_file("p.csv", data)
    assert [p.text for p in r.phrases] == ["Semicolon separated here."]


def test_xlsx_misnamed_as_xls_still_parses():
    """Exports are often mislabelled; fall back rather than fail."""
    r = parse_phrase_file("p.xls", _xlsx([["Mislabelled but valid."]]))
    assert [p.text for p in r.phrases] == ["Mislabelled but valid."]


def test_numeric_cells_become_text():
    r = parse_phrase_file("p.xlsx", _xlsx([[12345]]))
    assert r.phrases[0].text == "12345"


def test_empty_file_is_rejected():
    with pytest.raises(PhraseImportError):
        parse_phrase_file("p.xlsx", b"")


def test_unknown_file_type_is_rejected():
    with pytest.raises(PhraseImportError):
        parse_phrase_file("notes.pdf", b"%PDF-1.4 not a spreadsheet")


# ─── Endpoint ───────────────────────────────────────────────────────────
def test_import_adds_phrases(admin_headers):
    r = _upload(admin_headers, _xlsx([["Phrase"], ["Fresh import one."], ["Fresh import two."]]))
    assert r.status_code == 200
    d = r.json()
    assert d["added"] == 2 and d["duplicates"] == 0

    s = Session()
    try:
        assert s.query(Phrase).filter(Phrase.text == "Fresh import one.").count() == 1
    finally:
        s.close()


def test_import_reports_existing_phrases_as_duplicates(admin_headers):
    """Re-uploading a corrected file must not double up the bank."""
    s = Session()
    try:
        existing = s.query(Phrase).first().text
    finally:
        s.close()

    d = _upload(admin_headers, _xlsx([[existing], ["A brand new phrase here."]])).json()
    assert d["added"] == 1 and d["duplicates"] == 1
    assert any("already in the phrase bank" in x for x in d["details"])


def test_reimporting_the_same_file_adds_nothing(admin_headers):
    data = _xlsx([["Idempotent import phrase."]])
    assert _upload(admin_headers, data).json()["added"] == 1
    assert _upload(admin_headers, data).json()["added"] == 0


def test_import_rejects_a_bad_file(admin_headers):
    r = _upload(admin_headers, b"%PDF-1.4 nope", filename="notes.pdf")
    assert r.status_code == 400


def test_import_requires_admin():
    s = Session()
    try:
        u = User(first_name="No", last_name="Rights", date_of_birth=_dt.date(1990, 1, 1),
                 email="plain-import@example.com", auth_provider=AuthProvider.email,
                 password_hash="x")
        s.add(u)
        s.commit()
        uid = u.id
    finally:
        s.close()
    r = _upload({"Authorization": "Bearer " + create_access_token(uid)}, _xlsx([["Nope."]]))
    assert r.status_code == 403


# ─── Search ─────────────────────────────────────────────────────────────
def test_search_matches_case_insensitively(admin_headers):
    _upload(admin_headers, _xlsx([["Searchable Kingston phrase."]]))
    found = client.get("/admin/phrases?q=kingston", headers=admin_headers).json()
    assert any("Kingston" in p["text"] for p in found)


def test_search_with_no_match_is_empty(admin_headers):
    assert client.get("/admin/phrases?q=zzzznomatch", headers=admin_headers).json() == []


def test_search_can_exclude_inactive(admin_headers):
    _upload(admin_headers, _xlsx([["Hidden inactive phrase.", "en-JM", "no"]]))
    active = client.get("/admin/phrases?q=Hidden inactive&include_inactive=false",
                        headers=admin_headers).json()
    assert active == []
    both = client.get("/admin/phrases?q=Hidden inactive", headers=admin_headers).json()
    assert len(both) == 1 and both[0]["active"] is False
