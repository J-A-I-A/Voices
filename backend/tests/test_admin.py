"""Admin surface: access control, role changes, phrase bank, de-identified export."""
import datetime as _dt

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.phrase import Phrase
from app.models.user import AuthProvider, User
from app.models.voice_note import VoiceNote, VoiceNoteStatus
from app.security.token import create_access_token
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)


def _mk_user(email, *, admin=False, reviewer=False, dob=_dt.date(1990, 5, 4)) -> str:
    s = Session()
    try:
        u = User(first_name="Test", last_name="User", date_of_birth=dob, email=email,
                 auth_provider=AuthProvider.email, password_hash="x",
                 is_admin=admin, is_reviewer=reviewer)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def _auth(user_id: str) -> dict:
    return {"Authorization": "Bearer " + create_access_token(user_id)}


@pytest.fixture
def admin_headers():
    return _auth(_mk_user("admin@example.com", admin=True))


# ─── Access control ─────────────────────────────────────────────────────
def test_admin_endpoints_require_authentication():
    assert client.get("/admin/stats").status_code in (401, 403)


def test_plain_user_is_refused():
    headers = _auth(_mk_user("nobody@example.com"))
    for path in ("/admin/stats", "/admin/users", "/admin/phrases", "/admin/consents"):
        assert client.get(path, headers=headers).status_code == 403, path


def test_reviewer_is_not_an_admin():
    """Reviewer is a narrower role: it must not unlock the admin surface."""
    headers = _auth(_mk_user("rev@example.com", reviewer=True))
    assert client.get("/admin/users", headers=headers).status_code == 403


def test_admin_can_read(admin_headers):
    r = client.get("/admin/stats", headers=admin_headers)
    assert r.status_code == 200
    assert "users_total" in r.json()


def test_admin_inherits_reviewer_access(admin_headers):
    """An admin should not have to also be flagged a reviewer to work the queue."""
    assert client.get("/reviewer/queue", headers=admin_headers).status_code == 200


# ─── Roles ──────────────────────────────────────────────────────────────
def test_admin_can_grant_reviewer(admin_headers):
    uid = _mk_user("promote@example.com")
    r = client.patch(f"/admin/users/{uid}/roles", json={"is_reviewer": True}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["is_reviewer"] is True


def test_admin_cannot_demote_themselves(admin_headers):
    me = client.get("/admin/users", headers=admin_headers).json()["items"]
    admin_id = next(u["id"] for u in me if u["email"] == "admin@example.com")
    r = client.patch(f"/admin/users/{admin_id}/roles", json={"is_admin": False}, headers=admin_headers)
    assert r.status_code == 400
    assert "own admin access" in r.json()["detail"]


def test_last_admin_cannot_be_removed(admin_headers):
    """Losing every admin would lock the dashboard out permanently."""
    other = _mk_user("second-admin@example.com", admin=True)
    other_headers = _auth(other)
    admins = client.get("/admin/users", headers=admin_headers).json()["items"]
    first = next(u["id"] for u in admins if u["email"] == "admin@example.com")

    # Two admins exist, so removing one is allowed.
    assert client.patch(f"/admin/users/{first}/roles", json={"is_admin": False},
                        headers=other_headers).status_code == 200
    # `other` is now the only admin and may not remove itself either.
    assert client.patch(f"/admin/users/{other}/roles", json={"is_admin": False},
                        headers=other_headers).status_code == 400


def test_unknown_user_is_404(admin_headers):
    assert client.patch("/admin/users/does-not-exist/roles",
                        json={"is_reviewer": True}, headers=admin_headers).status_code == 404


# ─── Phrase bank ────────────────────────────────────────────────────────
def test_phrase_create_update_delete(admin_headers):
    r = client.post("/admin/phrases", json={"text": "Mi deh yah, yuh know."}, headers=admin_headers)
    assert r.status_code == 201
    pid = r.json()["id"]

    r = client.patch(f"/admin/phrases/{pid}", json={"active": False}, headers=admin_headers)
    assert r.status_code == 200 and r.json()["active"] is False

    assert client.delete(f"/admin/phrases/{pid}", headers=admin_headers).status_code == 204


def test_phrase_in_use_cannot_be_deleted(admin_headers):
    """Deleting it would orphan recordings from the text they were read against."""
    uid = _mk_user("speaker@example.com")
    s = Session()
    try:
        phrase = s.query(Phrase).first()
        s.add(VoiceNote(user_id=uid, phrase_id=phrase.id, s3_key="k.ogg",
                        mime_type="audio/ogg", status=VoiceNoteStatus.accepted))
        s.commit()
        pid = phrase.id
    finally:
        s.close()

    r = client.delete(f"/admin/phrases/{pid}", headers=admin_headers)
    assert r.status_code == 409
    assert "Deactivate it instead" in r.json()["detail"]


def test_phrase_text_is_validated(admin_headers):
    assert client.post("/admin/phrases", json={"text": "hi"}, headers=admin_headers).status_code == 422


# ─── Export ─────────────────────────────────────────────────────────────
def _seed_note(email="exporter@example.com", status=VoiceNoteStatus.accepted):
    uid = _mk_user(email, dob=_dt.date(1995, 3, 2))
    s = Session()
    try:
        phrase = s.query(Phrase).first()
        s.add(VoiceNote(user_id=uid, phrase_id=phrase.id, s3_key=f"voicenotes/{uid}/x.ogg",
                        mime_type="audio/ogg", status=status, duration_seconds=4,
                        qc={"transcript": "one love", "wer": 0.1}))
        s.commit()
    finally:
        s.close()
    return uid


def test_dataset_export_is_de_identified(admin_headers):
    uid = _seed_note()
    body = client.get("/admin/export/dataset?fmt=jsonl&status=accepted", headers=admin_headers).text

    for leak in ("exporter@example.com", "Test", "User", uid):
        assert leak not in body, f"export leaked {leak!r}"
    assert "spk_00001" in body
    assert '"age_band"' in body
    assert "audio_key" not in body, "raw S3 key embeds the user id and must be opt-in"


def test_export_can_include_internal_keys_on_request(admin_headers):
    uid = _seed_note()
    body = client.get(
        "/admin/export/dataset?fmt=jsonl&status=all&include_internal=true", headers=admin_headers
    ).text
    assert "audio_key" in body and uid in body


def test_export_accepted_only_excludes_other_statuses(admin_headers):
    _seed_note("a@example.com", VoiceNoteStatus.accepted)
    _seed_note("b@example.com", VoiceNoteStatus.rejected)
    accepted = client.get("/admin/export/dataset?status=accepted", headers=admin_headers).text
    assert accepted.count("\n") == 0 and "accepted" in accepted
    every = client.get("/admin/export/dataset?status=all", headers=admin_headers).text
    assert every.count("\n") == 1


def test_consent_register_csv_has_a_header(admin_headers):
    r = client.get("/admin/consents/export.csv", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text.splitlines()[0].startswith("consent_id,user_id,name,email")


# ─── Erasure ────────────────────────────────────────────────────────────
def test_erase_removes_recordings_but_keeps_the_account(admin_headers, monkeypatch):
    import app.routers.admin as adminmod
    deleted = []
    monkeypatch.setattr(adminmod, "delete_key", lambda key: deleted.append(key))

    uid = _seed_note("erase-me@example.com")
    r = client.post(f"/admin/users/{uid}/erase", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["notes_deleted"] == 1
    assert len(deleted) == 1

    s = Session()
    try:
        assert s.query(VoiceNote).filter(VoiceNote.user_id == uid).count() == 0
        # Account survives so the consent register stays auditable.
        assert s.get(User, uid) is not None
    finally:
        s.close()
