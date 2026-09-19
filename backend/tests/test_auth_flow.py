"""Integration test: register -> verify-OTP flow (uses the shared conftest DB)."""
import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import Session, engine

client = TestClient(app)

def _register(email='ada@example.com'):
    r = client.post('/auth/register/email', json={
        'first_name': 'Ada', 'last_name': 'Hall',
        'date_of_birth': '1990-01-01',
        'email': email, 'password': 'supersecret',
    })
    assert r.status_code == 200, r.text
    return r.json()['access_token'], r.json()['user']

def _register_token(email):
    return _register(email)[0]

def test_register_under_18_rejected():
    r = client.post('/auth/register/email', json={
        'first_name': 'Young', 'last_name': 'Person',
        'date_of_birth': str(date.today().year - 10) + '-01-01',
        'email': 'young@example.com', 'password': 'supersecret',
    })
    assert r.status_code == 400
    assert '18' in r.json()['detail']

def test_register_and_me():
    token, user = _register()
    assert user['email'] == 'ada@example.com'
    assert user['whatsapp_verified'] is False
    r = client.get('/auth/me', headers={'Authorization': 'Bearer ' + token})
    assert r.status_code == 200
    assert r.json()['first_name'] == 'Ada'

def test_verify_request_rejects_non_jamaican():
    token = _register_token('nonjm@example.com')
    h = {'Authorization': 'Bearer ' + token}
    r = client.post('/auth/verify/request', json={'phone': '2125551234'}, headers=h)
    assert r.status_code == 422

def test_full_otp_flow(monkeypatch):
    token = _register_token('otp1@example.com')
    h = {'Authorization': 'Bearer ' + token}
    sent = {}
    import app.routers.auth as authmod
    def fake_send_otp(num, code):
        sent['code'] = code
        async def ok(): return {'ok': True}
        return ok()
    monkeypatch.setattr(authmod, 'send_otp', fake_send_otp)
    r = client.post('/auth/verify/request', json={'phone': '8765551234'}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()['phone'] == '+18765551234'
    r = client.post('/auth/verify/check', json={'phone': '8765551234', 'code': sent['code']}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'verified'
    r = client.get('/auth/me', headers=h)
    assert r.json()['whatsapp_verified'] is True

def test_agent_link_requires_verification():
    token = _register_token('agent1@example.com')
    h = {'Authorization': 'Bearer ' + token}
    r = client.get('/auth/agent-link', headers=h)
    assert r.status_code == 403

def test_voice_notes_listed_only_after_verify(monkeypatch):
    token = _register_token('vn1@example.com')
    h = {'Authorization': 'Bearer ' + token}
    r = client.get('/voice-notes', headers=h)
    assert r.status_code == 403
    sent = {}
    import app.routers.auth as authmod
    def fake_send_otp(num, code):
        sent['code'] = code
        async def ok(): return {'ok': True}
        return ok()
    monkeypatch.setattr(authmod, 'send_otp', fake_send_otp)
    client.post('/auth/verify/request', json={'phone': '8765552222'}, headers=h)
    client.post('/auth/verify/check', json={'phone': '8765552222', 'code': sent['code']}, headers=h)
    r = client.get('/voice-notes', headers=h)
    assert r.status_code == 200
    assert r.json() == {'items': [], 'total': 0}
