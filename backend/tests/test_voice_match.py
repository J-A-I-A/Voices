"""Known-AI-voice check: matching, QC routing, and contributor redaction."""
import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

import app.config as cfg
import app.workers.qc as qcmod
from app.models.phrase import Phrase
from app.models.user import User
from app.models.voice_note import VoiceNote, VoiceNoteStatus
from app.routers.voice_notes import contributor_qc
from app.services import voice_match
from app.services.voice_match import best_match, voice_name_from_file

REFS_DIR = Path(__file__).resolve().parents[1] / "data" / "ai-voices"


def test_voice_name_from_file():
    assert voice_name_from_file("voice_preview_denzel - jamaican, raspy, and deep.mp3") == "denzel"
    assert voice_name_from_file("voice_preview_donovan wilson.mp3") == "donovan wilson"
    assert voice_name_from_file("custom.wav") == "custom"


def test_group_reference_files_by_file_and_folder(tmp_path):
    (tmp_path / "voice_preview_kevin - calm.mp3").write_bytes(b"")
    (tmp_path / "denzel").mkdir()
    (tmp_path / "denzel" / "01.mp3").write_bytes(b"")
    (tmp_path / "denzel" / "02.wav").write_bytes(b"")
    (tmp_path / "denzel" / "notes.txt").write_bytes(b"")
    (tmp_path / "empty").mkdir()
    groups = voice_match.group_reference_files(tmp_path)
    assert set(groups) == {"kevin", "denzel"}
    assert [p.name for p in groups["denzel"]] == ["01.mp3", "02.wav"]


def test_best_match_picks_highest_cosine():
    np = pytest.importorskip("numpy")
    refs = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])}
    score, name = best_match(np.array([0.6, 0.8]), refs)
    assert name == "b" and score == pytest.approx(0.8)


def test_contributor_qc_hides_ai_voice_details():
    qc = {
        "wer": 0.1, "ai_voice_score": 0.71, "ai_voice_closest": "denzel",
        "ai_voice_match": "denzel", "qc_stage_failed": "ai_voice",
        "qc_reason": "voice matches known AI voice 'denzel' (similarity 0.71)",
    }
    out = contributor_qc(qc)
    assert not any(k.startswith("ai_voice") for k in out)
    assert "denzel" not in str(out)
    assert out["qc_stage_failed"] == "manual_review"
    assert out["wer"] == 0.1
    assert contributor_qc(None) is None


# ── QC routing (model stubbed) ─────────────────────────────────

def _run_qc(monkeypatch, db_session, *, ai_result, wer_decision):
    monkeypatch.setattr(qcmod, "_download_to_tmp", lambda key, mime: tempfile.mkstemp()[1])
    monkeypatch.setattr(qcmod, "_prepare_wav", lambda src: tempfile.mkstemp(suffix=".wav")[1])
    monkeypatch.setattr(qcmod, "_stage1_analyze", lambda path: {"duration_seconds": 3.0})
    monkeypatch.setattr(qcmod, "check_ai_voice", lambda path: ai_result)

    async def fake_stage2(*a, **k):
        return {"transcript": "one love", "wer": 0.0, "asr_model": "stub", "decision": wer_decision}
    monkeypatch.setattr(qcmod, "_stage2_content", fake_stage2)

    user = db_session.query(User).first()
    phrase = db_session.query(Phrase).first()
    note = VoiceNote(user_id=user.id, phrase_id=phrase.id, s3_key="k.ogg", mime_type="audio/ogg")
    db_session.add(note)
    db_session.commit()
    asyncio.run(qcmod.run_qc_for_note(note.id))
    db_session.expire_all()
    return db_session.get(VoiceNote, note.id)


def test_ai_voice_match_holds_otherwise_accepted_note(monkeypatch, db_session):
    note = _run_qc(monkeypatch, db_session, wer_decision="accepted", ai_result={
        "ai_voice_score": 0.72, "ai_voice_closest": "denzel", "ai_voice_match": "denzel"})
    assert note.status == VoiceNoteStatus.needs_review
    assert note.qc["qc_stage_failed"] == "ai_voice"
    assert "denzel" in note.qc["qc_reason"]


def test_no_match_accepts_normally(monkeypatch, db_session):
    note = _run_qc(monkeypatch, db_session, wer_decision="accepted", ai_result={
        "ai_voice_score": 0.12, "ai_voice_closest": "kevin", "ai_voice_match": None})
    assert note.status == VoiceNoteStatus.accepted
    assert note.qc["ai_voice_score"] == 0.12


def test_ai_voice_match_does_not_rescue_rejected_note(monkeypatch, db_session):
    monkeypatch.setattr(cfg.settings, "wer_auto_reject", True)
    note = _run_qc(monkeypatch, db_session, wer_decision="rejected", ai_result={
        "ai_voice_score": 0.72, "ai_voice_closest": "denzel", "ai_voice_match": "denzel"})
    assert note.status == VoiceNoteStatus.rejected
    assert note.qc["ai_voice_match"] == "denzel"


def test_high_wer_goes_to_review_by_default(monkeypatch, db_session):
    monkeypatch.setattr(cfg.settings, "wer_auto_reject", False)
    note = _run_qc(monkeypatch, db_session, wer_decision="rejected", ai_result={
        "ai_voice_score": 0.1, "ai_voice_closest": "denzel", "ai_voice_match": None})
    assert note.status == VoiceNoteStatus.needs_review
    assert note.reject_reason is None
    assert note.qc["qc_stage_failed"] == "wer"


def test_high_wer_rejects_when_auto_reject_enabled(monkeypatch, db_session):
    monkeypatch.setattr(cfg.settings, "wer_auto_reject", True)
    note = _run_qc(monkeypatch, db_session, wer_decision="rejected", ai_result={
        "ai_voice_score": 0.1, "ai_voice_closest": "denzel", "ai_voice_match": None})
    assert note.status == VoiceNoteStatus.rejected
    assert note.reject_reason == "Recording did not match the assigned phrase."


def test_high_wer_with_ai_voice_match_is_reviewed_as_ai_voice(monkeypatch, db_session):
    monkeypatch.setattr(cfg.settings, "wer_auto_reject", False)
    note = _run_qc(monkeypatch, db_session, wer_decision="rejected", ai_result={
        "ai_voice_score": 0.72, "ai_voice_closest": "denzel", "ai_voice_match": "denzel"})
    assert note.status == VoiceNoteStatus.needs_review
    assert note.qc["qc_stage_failed"] == "ai_voice"


# ── Real model on the shipped reference voices ─────────────────

@pytest.fixture
def real_model():
    pytest.importorskip("sherpa_onnx")
    pytest.importorskip("soundfile")
    if not os.path.isfile(cfg.settings.speaker_model_path):
        pytest.skip("speaker model not installed (it is in the Docker image)")
    yield


def _to_opus_wav(src: str, start: float = 0.0) -> str:
    """Re-encode like a WhatsApp voice note, then decode as QC does."""
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    ogg = wav + ".ogg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", src,
                    "-c:a", "libopus", "-b:a", "16k", ogg], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", ogg,
                    "-ac", "1", "-ar", "16000", wav], check=True)
    os.remove(ogg)
    return wav


def test_every_reference_voice_is_flagged_after_whatsapp_encoding(real_model):
    for name, clips in voice_match.group_reference_files(REFS_DIR).items():
        wav = _to_opus_wav(str(clips[0]))
        try:
            result = voice_match.check_ai_voice(wav)
        finally:
            os.remove(wav)
        assert result["ai_voice_match"] == name, (name, result)


def test_synthetic_tone_is_not_flagged(real_model):
    np = pytest.importorskip("numpy")
    sf = pytest.importorskip("soundfile")
    sr = 16000
    t = np.linspace(0, 3, 3 * sr, endpoint=False)
    y = (0.3 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype("float32")
    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        sf.write(wav, y, sr)
        result = voice_match.check_ai_voice(wav)
    finally:
        os.remove(wav)
    assert result["ai_voice_match"] is None
