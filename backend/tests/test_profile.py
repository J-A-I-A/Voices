"""Self-service profile: rectify, unlink WhatsApp, withdraw consent, delete.

These are the Privacy Notice's contributor rights exercised without going
through the DPO.
"""
import datetime as _dt

import pytest
from fastapi.testclient import TestClient

import app.routers.profile as profilemod
from app.config import settings
from app.main import app
from app.models.consent import ConsentChannel, ConsentRecord
from app.models.user import AuthProvider, User
from app.models.voice_note import VoiceNote, VoiceNoteStatus
from app.models.phrase import Phrase
from app.security.token import create_access_token
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)


@pytest.fixture(autouse=True)
def no_s3(monkeypatch):
    """Never touch S3 from tests."""
    deleted = []
    monkeypatch.setattr(profilemod, "delete_key", lambda key: deleted.append(key))
    return deleted


_phone_seq = iter(range(1000, 9999))


def _mk_user(email="me@example.com", *, dob=_dt.date(1990, 6, 1), phone=..., verified=True) -> str:
    # whatsapp_number is unique, so each helper-made user needs its own.
    if phone is ...:
        phone = f"+1876555{next(_phone_seq)}"
    s = Session()
    try:
        u = User(first_name="Nanny", last_name="Maroon", date_of_birth=dob, email=email,
                 auth_provider=AuthProvider.email, password_hash="x",
                 whatsapp_number=phone, whatsapp_verified=verified)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


def _auth(uid):
    return {"Authorization": "Bearer " + create_access_token(uid)}


def _give_consent(uid):
    s = Session()
    try:
        s.add(ConsentRecord(user_id=uid, policy_version=settings.privacy_policy_version,
                            channel=ConsentChannel.whatsapp, evidence="I AGREE",
                            phone="+18765551111"))
        s.commit()
    finally:
        s.close()


def _add_note(uid):
    s = Session()
    try:
        p = s.query(Phrase).first()
        s.add(VoiceNote(user_id=uid, phrase_id=p.id, s3_key=f"voicenotes/{uid}/a.ogg",
                        mime_type="audio/ogg", status=VoiceNoteStatus.accepted))
        s.commit()
    finally:
        s.close()


# ─── Rectify ────────────────────────────────────────────────────────────
def test_can_change_name():
    uid = _mk_user()
    r = client.patch("/profile", json={"first_name": "Queen", "last_name": "Nanny"},
                     headers=_auth(uid))
    assert r.status_code == 200
    assert r.json()["first_name"] == "Queen" and r.json()["last_name"] == "Nanny"


def test_changing_dob_below_18_is_refused():
    """The age gate is enforced on edit, not just at registration."""
    uid = _mk_user()
    young = (_dt.date.today() - _dt.timedelta(days=365 * 14)).isoformat()
    r = client.patch("/profile", json={"date_of_birth": young}, headers=_auth(uid))
    assert r.status_code == 403

    s = Session()
    try:
        assert s.get(User, uid).date_of_birth == _dt.date(1990, 6, 1)
    finally:
        s.close()


def test_profile_requires_authentication():
    assert client.patch("/profile", json={"first_name": "X"}).status_code in (401, 403)


# ─── WhatsApp ───────────────────────────────────────────────────────────
def test_can_unlink_whatsapp_number():
    uid = _mk_user()
    r = client.delete("/profile/whatsapp", headers=_auth(uid))
    assert r.status_code == 200
    body = r.json()
    assert body["whatsapp_number"] is None and body["whatsapp_verified"] is False


def test_unlinking_keeps_existing_recordings():
    """Removing the number stops collection; it is not a deletion request."""
    uid = _mk_user()
    _add_note(uid)
    client.delete("/profile/whatsapp", headers=_auth(uid))
    s = Session()
    try:
        assert s.query(VoiceNote).filter(VoiceNote.user_id == uid).count() == 1
    finally:
        s.close()


def test_unlinking_without_a_number_is_a_400():
    uid = _mk_user(phone=None, verified=False)
    assert client.delete("/profile/whatsapp", headers=_auth(uid)).status_code == 400


# ─── Consent ────────────────────────────────────────────────────────────
def test_consent_status_reports_active_consent():
    uid = _mk_user()
    _give_consent(uid)
    d = client.get("/profile/consent", headers=_auth(uid)).json()
    assert d["has_consent"] is True
    assert d["policy_version"] == settings.privacy_policy_version


def test_can_withdraw_consent():
    uid = _mk_user()
    _give_consent(uid)
    r = client.post("/profile/consent/withdraw", headers=_auth(uid))
    assert r.status_code == 200 and r.json()["has_consent"] is False

    s = Session()
    try:
        rec = s.query(ConsentRecord).filter(ConsentRecord.user_id == uid).one()
        # Append-only: the row is marked, never deleted.
        assert rec.withdrawn_at is not None
    finally:
        s.close()


def test_withdrawing_without_consent_is_a_400():
    uid = _mk_user()
    assert client.post("/profile/consent/withdraw", headers=_auth(uid)).status_code == 400


# ─── Delete ─────────────────────────────────────────────────────────────
def test_delete_removes_recordings_and_scrubs_identity(no_s3):
    uid = _mk_user("gone@example.com")
    _give_consent(uid)
    _add_note(uid)

    r = client.delete("/profile", headers=_auth(uid))
    assert r.status_code == 200
    d = r.json()
    assert d["deleted"] is True and d["notes_deleted"] == 1
    assert no_s3 == [f"voicenotes/{uid}/a.ogg"]

    s = Session()
    try:
        u = s.get(User, uid)
        assert u.deleted_at is not None
        assert u.first_name == "Deleted" and u.last_name == "user"
        assert "gone@example.com" not in u.email
        assert u.whatsapp_number is None and u.google_subject is None
        assert u.is_admin is False and u.is_reviewer is False
        assert s.query(VoiceNote).filter(VoiceNote.user_id == uid).count() == 0
    finally:
        s.close()


def test_delete_keeps_an_anonymous_consent_record():
    """The register must still evidence that consent was given and withdrawn."""
    uid = _mk_user("audit@example.com")
    _give_consent(uid)
    client.delete("/profile", headers=_auth(uid))

    s = Session()
    try:
        rec = s.query(ConsentRecord).filter(ConsentRecord.user_id == uid).one()
        assert rec.withdrawn_at is not None
        assert rec.phone is None, "phone number survived deletion"
    finally:
        s.close()


def test_token_stops_working_after_deletion():
    uid = _mk_user("dead@example.com")
    headers = _auth(uid)
    assert client.delete("/profile", headers=headers).status_code == 200
    # The same token must not keep working.
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.patch("/profile", json={"first_name": "X"}, headers=headers).status_code == 401


def test_deleted_account_cannot_log_in_again():
    uid = _mk_user("relogin@example.com")
    client.delete("/profile", headers=_auth(uid))
    r = client.post("/auth/login", json={"email": "relogin@example.com", "password": "x"})
    assert r.status_code == 401


def test_deleting_twice_is_refused():
    uid = _mk_user("twice@example.com")
    headers = _auth(uid)
    assert client.delete("/profile", headers=headers).status_code == 200
    assert client.delete("/profile", headers=headers).status_code == 401


def test_deleted_users_do_not_appear_in_admin_lists():
    admin_id = _mk_user("adm@example.com")
    s = Session()
    try:
        s.get(User, admin_id).is_admin = True
        s.commit()
    finally:
        s.close()

    victim = _mk_user("vanish@example.com")
    client.delete("/profile", headers=_auth(victim))

    listing = client.get("/admin/users", headers=_auth(admin_id)).json()
    assert all(u["id"] != victim for u in listing["items"])
