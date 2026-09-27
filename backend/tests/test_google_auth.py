"""Google sign-in must only ask for details it does not already have.

The portal used to route every Google sign-in through the completion form, and
the request schema made date_of_birth mandatory, so returning users were asked
for their name and date of birth on every sign-in. These tests pin the fixed
behaviour.
"""
import datetime as _dt

import pytest
from fastapi.testclient import TestClient

import app.routers.auth as authmod
from app.main import app
from app.models.user import AuthProvider, User
from tests.conftest import Session, engine  # noqa: F401

client = TestClient(app)


@pytest.fixture(autouse=True)
def fake_google(monkeypatch):
    """Stub Google token verification; no network, no real credentials."""
    async def _verify(id_token: str):
        # The stub encodes the identity in the token itself: "tok:<email>".
        email = id_token.split(":", 1)[1] if ":" in id_token else "someone@example.com"
        return {"email": email, "sub": "google-sub-" + email,
                "given_name": "Marcus", "family_name": "Garvey"}

    monkeypatch.setattr(authmod, "verify_id_token", _verify)


def _google(email, **body):
    return client.post("/auth/google", json={"id_token": "tok:" + email, **body})


def _mk_google_user(email, dob=_dt.date(1990, 1, 1)):
    s = Session()
    try:
        u = User(first_name="Existing", last_name="User", date_of_birth=dob, email=email,
                 auth_provider=AuthProvider.google, google_subject="google-sub-" + email)
        s.add(u)
        s.commit()
        return u.id
    finally:
        s.close()


# ─── New accounts ───────────────────────────────────────────────────────
def test_new_user_is_asked_to_complete():
    r = _google("new@example.com")
    assert r.status_code == 200
    d = r.json()
    assert d["requires_completion"] is True
    assert d["access_token"] is None
    # Prefill comes back so the form is not blank.
    assert d["first_name"] == "Marcus" and d["last_name"] == "Garvey"


def test_no_account_is_created_until_details_are_given():
    _google("nothing-yet@example.com")
    s = Session()
    try:
        assert s.query(User).filter(User.email == "nothing-yet@example.com").count() == 0
    finally:
        s.close()


def test_completion_creates_the_account():
    r = _google("finishing@example.com", date_of_birth="1992-07-14",
                first_name="Marcus", last_name="Garvey")
    assert r.status_code == 200
    d = r.json()
    assert d["requires_completion"] is False
    assert d["access_token"] and d["user"]["email"] == "finishing@example.com"


def test_under_18_is_rejected_on_completion():
    too_young = (_dt.date.today() - _dt.timedelta(days=365 * 15)).isoformat()
    r = _google("child@example.com", date_of_birth=too_young)
    assert r.status_code in (400, 403, 422)


# ─── Returning accounts — the actual bug ────────────────────────────────
def test_returning_user_signs_in_without_being_asked_again():
    _mk_google_user("back@example.com")
    r = _google("back@example.com")
    assert r.status_code == 200
    d = r.json()
    assert d["requires_completion"] is False, "returning user was asked to complete again"
    assert d["access_token"]
    assert d["user"]["email"] == "back@example.com"


def test_returning_sign_in_does_not_overwrite_stored_details():
    """A plain sign-in must not rewrite the name or date of birth on file."""
    uid = _mk_google_user("stable@example.com", dob=_dt.date(1985, 4, 2))
    _google("stable@example.com")
    s = Session()
    try:
        u = s.get(User, uid)
        assert u.first_name == "Existing" and u.last_name == "User"
        assert u.date_of_birth == _dt.date(1985, 4, 2)
    finally:
        s.close()


def test_returning_user_keeps_their_roles():
    uid = _mk_google_user("boss@example.com")
    s = Session()
    try:
        u = s.get(User, uid)
        u.is_admin = True
        s.commit()
    finally:
        s.close()

    assert _google("boss@example.com").json()["user"]["is_admin"] is True


def test_account_without_a_dob_is_asked_for_one():
    """Only the genuinely missing piece is requested, with names prefilled."""
    s = Session()
    try:
        u = User(first_name="No", last_name="Birthday", date_of_birth=None,
                 email="nodob@example.com", auth_provider=AuthProvider.google)
        s.add(u)
        s.commit()
    except Exception:
        s.rollback()
        pytest.skip("date_of_birth is non-nullable in this schema")
    finally:
        s.close()

    d = _google("nodob@example.com").json()
    assert d["requires_completion"] is True
    assert d["first_name"] == "No"


def test_password_account_cannot_sign_in_with_google():
    s = Session()
    try:
        s.add(User(first_name="Pass", last_name="Word", date_of_birth=_dt.date(1990, 1, 1),
                   email="pw@example.com", auth_provider=AuthProvider.email, password_hash="x"))
        s.commit()
    finally:
        s.close()

    r = _google("pw@example.com")
    assert r.status_code == 409
