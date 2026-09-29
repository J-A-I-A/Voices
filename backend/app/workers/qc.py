"""Automated quality control pipeline for a single VoiceNote.

Stage 1 — Fast structural/signal checks (no ML, milliseconds):
  decodability, duration bounds, VAD ratio, loudness & clipping, SNR, format.
Stage 2 — Content verification (ASR + WER vs assigned phrase):
  three-way thresholds → accepted / rejected / needs_review.
Known-AI-voice check (after Stage 1): speaker-embedding match against the
  reference voices in data/ai-voices. A match never auto-accepts — it holds
  the note for a reviewer.
Stage 3 — (designed for, not built): language ID, single-speaker, duplicates,
  general synthetic/replay detection. Hooks provided below.

All output is persisted on VoiceNote.qc.
"""
from __future__ import annotations

import datetime as _dt
import logging
import os
import subprocess
import tempfile
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..db import session_scope
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..services import s3 as s3_svc
from ..services.asr import transcribe
from ..services.voice_match import check_ai_voice
from ..services.wer import compute_wer, normalize

logger = logging.getLogger("carib.qc")


class QCFail(Exception):
    """Raised when a Stage-1 check fails; carries qc_stage_failed + reason."""
    def __init__(self, stage: str, reason: str, metrics: dict | None = None):
        super().__init__(reason)
        self.stage = stage
        self.reason = reason
        self.metrics = metrics or {}


# ─────────────────────────────────────────────────────────────
#  Stage 3 extension points (designed for, implemented LATER)
# ─────────────────────────────────────────────────────────────

def run_stage3_checks(audio_path: str, phrase_text: str) -> dict:
    """Hook for future ML checks. Returns extra metrics; never raises today.

    Planned: language/dialect ID (English/Patois vs off-target), single-speaker
    check via pyannote diarization (reject multi-voice / recording-of-a-recording),
    duplicate detection via chromaprint fingerprint or speaker embeddings,
    synthetic/replay (TTS) detection.
    """
    return {}


# ─────────────────────────────────────────────────────────────
#  Stage 1: fast structural/signal checks
# ─────────────────────────────────────────────────────────────

def _stage1_analyze(audio_path: str) -> dict:
    """Run all fast checks. Raises QCFail on a hard rejection; returns metrics."""
    metrics: dict[str, Any] = {}

    # --- Decodability + format via librosa ---
    try:
        import librosa
        import numpy as np
        import soundfile as sf
    except Exception as e:  # pragma: no cover
        raise QCFail("decodability", f"audio analysis libraries unavailable: {e}")

    try:
        y, sr = librosa.load(audio_path, sr=None, mono=True)
    except Exception as e:
        raise QCFail("decodability", f"file could not be decoded: {e}")
    if y is None or len(y) == 0:
        raise QCFail("decodability", "empty or corrupt audio")

    duration = float(len(y)) / float(sr)
    metrics["duration_seconds"] = round(duration, 2)
    metrics["sample_rate"] = int(sr)
    metrics["channels"] = 1  # we loaded mono

    # --- Duration bounds ---
    if duration < settings.min_duration_s:
        raise QCFail("duration", "recording is too short (under 1 second).", metrics)
    if duration > settings.max_duration_s:
        raise QCFail("duration", "recording is too long.", metrics)

    # --- Voice-activity ratio via WebRTC VAD ---
    import numpy as np
    vad_ratio = _vad_ratio(y, sr)
    metrics["vad_ratio"] = round(vad_ratio, 3)
    if vad_ratio < settings.min_vad_ratio:
        raise QCFail("vad", "recording is mostly silent — no speech detected.", metrics)

    # --- Loudness (dBFS) + clipping ---
    peak = float(np.max(np.abs(y)) + 1e-12)
    rms = float(np.sqrt(np.mean(y ** 2)) + 1e-12)
    loudness_dbfs = 20.0 * float(np.log10(rms))
    metrics["loudness_dbfs"] = round(loudness_dbfs, 2)
    # Clipping: samples at/very near ±1.0
    clip_ratio = float(np.mean(np.abs(y) >= 0.99))
    metrics["clipping_ratio"] = round(clip_ratio, 4)
    if loudness_dbfs < settings.min_loudness_dbfs:
        raise QCFail("loudness", "recording is too quiet.", metrics)
    if loudness_dbfs > settings.max_loudness_dbfs:
        raise QCFail("loudness", "recording is too loud (clipping risk).", metrics)
    if clip_ratio > settings.max_clipping_ratio:
        raise QCFail("clipping", "recording is clipped/distorted.", metrics)

    # --- SNR estimate (noise floor from low-energy frames) ---
    snr_db = _estimate_snr(y, sr)
    metrics["snr_db"] = round(snr_db, 2)
    if snr_db < settings.min_snr_db:
        # Flag low-SNR: not an outright reject here but feed into Stage 2 review weight.
        metrics["low_snr"] = True

    return metrics


def _vad_ratio(y, sr: int) -> float:
    """Share of frames classified as speech by WebRTC VAD. Falls back to energy."""
    try:
        import webrtcvad
        import numpy as np
        vad = webrtcvad.Vad(2)  # 0..3, 2 = fairly aggressive
        # WebRTC VAD needs 8/16/32kHz, 10/20/30ms frames.
        target_sr = 16000 if sr in (8000, 16000, 32000) else 16000
        if sr != target_sr:
            import librosa
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
            sr = target_sr
        frame_len = int(0.030 * sr)  # 30ms
        if frame_len < 1:
            return 0.0
        frames = [y[i:i + frame_len] for i in range(0, len(y) - frame_len + 1, frame_len)]
        if not frames:
            return 0.0
        voiced = 0
        for fr in frames:
            pcm = (fr * 32768.0).astype("int16").tobytes()
            try:
                if vad.is_speech(pcm, sr):
                    voiced += 1
            except Exception:
                pass
        return voiced / len(frames)
    except Exception:
        # Energy-based fallback: frames above mean energy are "voiced-ish".
        import numpy as np
        frame_len = max(1, int(0.030 * sr))
        frames = [y[i:i + frame_len] for i in range(0, len(y) - frame_len + 1, frame_len)]
        if not frames:
            return 0.0
        energies = np.array([np.mean(fr ** 2) for fr in frames])
        thr = np.mean(energies) * 0.5
        return float(np.mean(energies > thr))


def _estimate_snr(y, sr: int) -> float:
    """Rough SNR in dB: signal RMS over noise floor RMS, derived from low-energy frames."""
    import numpy as np
    frame_len = max(1, int(0.030 * sr))
    frames = [y[i:i + frame_len] for i in range(0, len(y) - frame_len + 1, frame_len)]
    if not frames:
        return 0.0
    energies = np.array([np.sqrt(np.mean(fr ** 2)) for fr in frames])
    energies.sort()
    # noise floor = 10th percentile of frame RMS; signal = 90th percentile.
    noise = float(np.percentile(energies, 10) + 1e-9)
    signal = float(np.percentile(energies, 90) + 1e-9)
    return 20.0 * float(np.log10(signal / noise))


# ─────────────────────────────────────────────────────────────
#  Stage 2: content verification (ASR + WER)
# ─────────────────────────────────────────────────────────────

async def _stage2_content(audio_path: str, phrase_text: str, mime: str, audio_bytes: bytes) -> dict:
    """Transcribe and compute WER. Returns {transcript, wer, asr_model, decision}."""
    asr = await transcribe(audio_bytes, mime_type=mime)
    transcript = asr["text"] or ""
    wer = compute_wer(phrase_text, transcript)
    decision = _wer_decision(wer)
    return {
        "transcript": transcript,
        "wer": round(wer, 4),
        "asr_model": asr["model"],
        "decision": decision,
    }


def _wer_decision(wer: float) -> str:
    if wer <= settings.wer_accept_max:
        return "accepted"
    if wer >= settings.wer_reject_min:
        return "rejected"
    return "needs_review"


# ─────────────────────────────────────────────────────────────
#  Orchestration
# ─────────────────────────────────────────────────────────────

async def run_qc_for_note(voice_note_id: str) -> None:
    """Full QC for one note. Downloads from S3, runs Stage 1 → 2, persists result."""
    with session_scope() as db:
        note = db.get(VoiceNote, voice_note_id)
        if not note:
            logger.warning("qc: note %s not found", voice_note_id)
            return
        phrase_text = note.phrase.text if note.phrase else ""
        mime = note.mime_type or "audio/ogg"

        # 1) Fetch the audio bytes from S3 to a temp file.
        tmp_path = _download_to_tmp(note.s3_key, mime)
        wav_path: str | None = None
        try:
            # Decode to 16kHz mono WAV up front (robust OGG/Opus via ffmpeg).
            wav_path = _prepare_wav(tmp_path)
            qc: dict[str, Any] = {}
            try:
                stage1 = _stage1_analyze(wav_path)
                qc.update(stage1)
            except QCFail as f:
                _finalize(
                    db, note, VoiceNoteStatus.rejected, reason=f.reason,
                    qc={**qc, **f.metrics, "qc_stage_failed": f.stage, "qc_reason": f.reason,
                        "checked_at": _now_iso()},
                )
                return

            # 1b) Known AI voices. Runs before ASR so the result is on record
            # even if transcription fails below.
            try:
                qc.update(check_ai_voice(wav_path))
            except Exception as e:
                logger.exception("ai-voice check failed for %s: %s", note.id, e)
                qc["ai_voice_check"] = f"error: {e}"
            ai_match = qc.get("ai_voice_match")

            # 2) Stage 2 — content (ASR/WER). Only run on survivors.
            with open(wav_path, "rb") as f:
                audio_bytes = f.read()
            try:
                stage2 = await _stage2_content(wav_path, phrase_text, "audio/wav", audio_bytes)
            except Exception as e:
                logger.exception("stage2 ASR failed for %s: %s", note.id, e)
                _finalize(
                    db, note, VoiceNoteStatus.needs_review,
                    reason="ASR transcription failed; needs manual review.",
                    qc={**qc, "qc_stage_failed": "asr", "qc_reason": str(e),
                        "checked_at": _now_iso()},
                )
                return

            qc["transcript"] = stage2["transcript"]
            qc["wer"] = stage2["wer"]
            qc["asr_model"] = stage2["asr_model"]

            # 3) Stage 3 extension points (no-ops today).
            try:
                qc.update(run_stage3_checks(tmp_path, phrase_text))
            except Exception as e:
                logger.warning("stage3 hook errored (ignored): %s", e)

            decision = stage2["decision"]
            if ai_match and decision != "rejected":
                # Flag only: a reviewer confirms. A note that fails WER is
                # rejected anyway; the match stays recorded in qc.
                _finalize(
                    db, note, VoiceNoteStatus.needs_review,
                    qc={**qc, "qc_stage_failed": "ai_voice",
                        "qc_reason": f"voice matches known AI voice '{ai_match}' "
                                     f"(similarity {qc['ai_voice_score']})",
                        "checked_at": _now_iso()},
                )
            elif decision == "accepted":
                _finalize(db, note, VoiceNoteStatus.accepted, qc={**qc, "checked_at": _now_iso()})
            elif decision == "rejected":
                _finalize(
                    db, note, VoiceNoteStatus.rejected,
                    reason="Recording did not match the assigned phrase.",
                    qc={**qc, "qc_stage_failed": "wer", "qc_reason": "high WER",
                        "checked_at": _now_iso()},
                )
            else:
                _finalize(
                    db, note, VoiceNoteStatus.needs_review,
                    qc={**qc, "qc_stage_failed": None, "qc_reason": "middle WER band",
                        "checked_at": _now_iso()},
                )
        finally:
            for p in (tmp_path, wav_path):
                if p:
                    try:
                        os.remove(p)
                    except OSError:
                        pass


def _download_to_tmp(s3_key: str, mime: str) -> str:
    """Download an S3 object to a temp file with a sensible extension."""
    ext = _ext_for_mime(mime)
    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    obj = s3_svc.client().get_object(Bucket=settings.s3_bucket, Key=s3_key)
    with open(tmp_path, "wb") as f:
        for chunk in obj["Body"].iter_chunks(8192):
            f.write(chunk)
    return tmp_path


def _ext_for_mime(mime: str) -> str:
    return {
        "audio/ogg": ".ogg", "audio/ogg; codecs=opus": ".ogg",
        "audio/mpeg": ".mp3", "audio/mp4": ".m4a",
        "audio/webm": ".webm", "audio/wav": ".wav",
    }.get(mime, ".bin")


def _prepare_wav(src_path: str) -> str:
    """Decode any audio to 16kHz mono WAV with ffmpeg (robust OGG/Opus handling).

    Returns the path to the converted WAV. Raises QCFail("decodability", ...) if
    ffmpeg cannot decode the file — this is the single decodability gate, used by
    Stage 1.
    """
    wav = src_path + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src_path, "-ac", "1", "-ar", "16000", wav],
            check=True, capture_output=True,
        )
    except FileNotFoundError as e:
        raise QCFail("decodability", f"ffmpeg not available: {e}")
    except subprocess.CalledProcessError as e:
        raise QCFail(
            "decodability",
            "file could not be decoded (ffmpeg failed).",
        ) from e
    return wav


def _now_iso() -> str:
    """ISO-8601 string, not a datetime.

    The value goes into the `qc` JSONB column, and psycopg serialises that
    with json.dumps — a raw datetime raises "Object of type datetime is not
    JSON serializable" and aborts the whole QC run. The portal also types
    QCMetadata.checked_at as a string.
    """
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _finalize(db: Session, note: VoiceNote, status: VoiceNoteStatus,
              *, reason: str | None = None, qc: dict) -> None:
    note.status = status
    note.reject_reason = reason if status == VoiceNoteStatus.rejected else None
    note.qc = qc
    # Mirror the measured duration onto the column the dashboard reads for its
    # duration chip; QC only had it inside the qc payload.
    if note.duration_seconds is None:
        measured = qc.get("duration_seconds")
        if isinstance(measured, (int, float)):
            note.duration_seconds = int(round(measured))
    db.commit()
    logger.info("qc done for note %s → %s", note.id, status.value)


# CLI entrypoint: python -m app.workers.qc_job <note_id>
if __name__ == "__main__":  # pragma: no cover
    import asyncio as _a, sys as _sys
    _a.run(run_qc_for_note(_sys.argv[1]))
