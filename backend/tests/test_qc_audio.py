"""QC Stage 1 audio analysis test using a synthesized WAV.

Skips automatically if numpy/soundfile/librosa are unavailable (they ARE
in the Docker image; this sandbox venv just lacks the heavy audio deps).
"""
import os
import tempfile

import pytest

np = pytest.importorskip('numpy')
sf = pytest.importorskip('soundfile')
librosa = pytest.importorskip('librosa')
webrtcvad = pytest.importorskip('webrtcvad')

from app.workers.qc import _stage1_analyze, QCFail


def _write_tone_wav(path, seconds=2.0, sr=16000, freq=220):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    # Amplitude-modulated tone so VAD sees energy; not pure silence.
    tone = 0.3 * np.sin(2 * np.pi * freq * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 2 * t))
    tone = tone.astype('float32')
    sf.write(path, tone, sr)


def test_stage1_accepts_clean_tone(monkeypatch):
    # Use permissive thresholds so a synthesized tone passes.
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, 'min_duration_s', 0.5)
    monkeypatch.setattr(cfg.settings, 'max_duration_s', 60)
    monkeypatch.setattr(cfg.settings, 'min_vad_ratio', 0.0)
    monkeypatch.setattr(cfg.settings, 'min_snr_db', 0.0)
    monkeypatch.setattr(cfg.settings, 'min_loudness_dbfs', -60.0)
    monkeypatch.setattr(cfg.settings, 'max_loudness_dbfs', 0.0)
    monkeypatch.setattr(cfg.settings, 'max_clipping_ratio', 1.0)

    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        _write_tone_wav(path)
        metrics = _stage1_analyze(path)
        assert metrics['duration_seconds'] >= 1.5
        assert 'loudness_dbfs' in metrics
        assert 'vad_ratio' in metrics
    finally:
        os.remove(path)


def test_stage1_rejects_too_short(monkeypatch):
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, 'min_duration_s', 5.0)
    fd, path = tempfile.mkstemp(suffix='.wav')
    os.close(fd)
    try:
        _write_tone_wav(path, seconds=1.0)
        with pytest.raises(QCFail) as exc:
            _stage1_analyze(path)
        assert exc.value.stage == 'duration'
    finally:
        os.remove(path)
