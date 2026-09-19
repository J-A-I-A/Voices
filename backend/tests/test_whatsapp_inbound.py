"""Inbound WhatsApp voice-note handling: phrase + S3 + QC enqueue (shared conftest DB)."""
import json, hmac, hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import Session

client = TestClient(app)
BOB = '18765550001'  # the verified user seeded by conftest

def _sign(body: bytes) -> dict:
    return {'X-Hub-Signature-256': 'sha256=' + hmac.new(b'secret', body, hashlib.sha256).hexdigest(), 'Content-Type': 'application/json'}

def _msg(msg_type='text', from_num=BOB, **kw):
    m = {'from': from_num, 'id': 'wamid.' + kw.get('id', 'abc'), 'type': msg_type}
    if msg_type in ('audio','voice'):
        m[msg_type] = {'id': kw.get('media_id', 'media_1'), 'mime_type': 'audio/ogg'}
    elif msg_type == 'text':
        m['text'] = {'body': kw.get('body', 'hi')}
    return m

def _envelope(messages, from_num=BOB):
    return {'object': 'whatsapp_business_account', 'entry': [{'id':'1','changes': [{'value': {'messaging_product':'whatsapp','contacts':[{'wa_id': from_num,'name':'Bob'}], 'messages': messages}}]}]}

def test_unknown_sender_told_to_register(monkeypatch):
    sent = []
    import app.services.whatsapp as wasvc
    async def fake_send(num, body): sent.append((num, body)); return {}
    monkeypatch.setattr(wasvc, 'send_text', fake_send)
    body = json.dumps(_envelope([_msg('text', from_num='18769999999')], from_num='18769999999')).encode()
    r = client.post('/whatsapp/webhook', content=body, headers=_sign(body))
    assert r.status_code == 200
    assert any('register' in b.lower() for _, b in sent)

def test_text_message_assigns_phrase(monkeypatch):
    sent = []
    import app.services.whatsapp as wasvc
    async def fake_send(num, body): sent.append((num, body)); return {}
    monkeypatch.setattr(wasvc, 'send_text', fake_send)
    body = json.dumps(_envelope([_msg('text', body='hi')])).encode()
    r = client.post('/whatsapp/webhook', content=body, headers=_sign(body))
    assert r.status_code == 200
    assert any('phrase' in b.lower() for _, b in sent)
    from app.models.user import User
    s = Session()
    u = s.query(User).filter_by(whatsapp_number='+'+BOB).first()
    assert u.pending_phrase_id is not None
    s.close()

def test_voice_note_uploaded_and_qc_enqueued(monkeypatch):
    sent = []; enqueued = []
    import app.routers.whatsapp as wamod
    import app.services.whatsapp as wasvc
    async def fake_send(num, body): sent.append((num, body)); return {}
    async def fake_fetch(media_id): return (b'OGGDATA', 'audio/ogg')
    def fake_upload(key, data, mime_type=None): return key
    async def fake_enqueue(note_id): enqueued.append(note_id)
    monkeypatch.setattr(wasvc, 'send_text', fake_send)
    monkeypatch.setattr(wasvc, 'fetch_media_bytes', fake_fetch)
    monkeypatch.setattr(wamod, 'upload_bytes', fake_upload)
    monkeypatch.setattr(wamod, 'enqueue_qc', fake_enqueue)
    # assign a phrase first
    body = json.dumps(_envelope([_msg('text', body='hi')])).encode()
    client.post('/whatsapp/webhook', content=body, headers=_sign(body))
    # then send the voice note
    vbody = json.dumps(_envelope([_msg('audio', id='vnote', media_id='media_xyz')])).encode()
    r = client.post('/whatsapp/webhook', content=vbody, headers=_sign(vbody))
    assert r.status_code == 200, r.text
    assert any('received' in b.lower() for _, b in sent)
    assert len(enqueued) == 1
    from app.models.voice_note import VoiceNote, VoiceNoteStatus
    s = Session()
    notes = s.query(VoiceNote).all()
    assert len(notes) == 1
    n = notes[0]
    assert n.status == VoiceNoteStatus.received
    assert n.s3_key.startswith('voicenotes/') and n.s3_key.endswith('.ogg')
    assert n.phrase_id is not None and n.whatsapp_message_id == 'wamid.vnote'
    s.close()
