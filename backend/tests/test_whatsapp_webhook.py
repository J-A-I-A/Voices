"""WhatsApp webhook: verify-token handshake + signature verification (shared conftest)."""
import json, hmac, hashlib

from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import engine

client = TestClient(app)

@property
def _unused(self): return None

def test_webhook_handshake_ok():
    r = client.get('/whatsapp/webhook', params={'hub.mode': 'subscribe', 'hub.verify_token': 'vt', 'hub.challenge': '12345'})
    assert r.status_code == 200
    assert r.json() == 12345

def test_webhook_handshake_bad_token():
    r = client.get('/whatsapp/webhook', params={'hub.mode': 'subscribe', 'hub.verify_token': 'wrong', 'hub.challenge': '12345'})
    assert r.status_code == 403

def test_webhook_post_invalid_signature_rejected():
    payload = json.dumps({'object': 'whatsapp_business_account', 'entry': []}).encode()
    r = client.post('/whatsapp/webhook', content=payload, headers={'X-Hub-Signature-256': 'sha256=deadbeef', 'Content-Type': 'application/json'})
    assert r.status_code == 401

def test_webhook_post_valid_signature_accepted():
    payload = json.dumps({'object': 'whatsapp_business_account', 'entry': []}).encode()
    sig = 'sha256=' + hmac.new(b'secret', payload, hashlib.sha256).hexdigest()
    r = client.post('/whatsapp/webhook', content=payload, headers={'X-Hub-Signature-256': sig, 'Content-Type': 'application/json'})
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'
