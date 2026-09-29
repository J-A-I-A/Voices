"""Known-AI-voice detection via speaker embeddings.

Each reference clip in `settings.ai_voice_refs_dir` (e.g. ElevenLabs voice
previews) is turned into a speaker embedding once, on first use. A submitted
note's embedding is compared against all of them by cosine similarity; a
score at or above `settings.ai_voice_match_threshold` means the recording is
very likely that synthetic voice.

Model: NeMo TitaNet-small (ONNX, run through sherpa-onnx — CPU only, no torch).
Calibrated with everything re-encoded as 16 kbps Opus (WhatsApp-like), using
the preview + 4 generated clips per voice as references and 2 more clips per
voice held out:
  - held-out AI clips, full (~7 s) and 3 s crops: 0.64–0.89, always the
    right voice;
  - 8.5 min of two real Jamaican speakers in 3/5/10 s windows: ≤ 0.49
    (one speaker sits near 'denzel' — 0.40 would flag 2.4% of their clips).
Hence the 0.55 default threshold, between the two.

To add a voice, drop its audio file into the refs directory — or a folder of
clips named after the voice (their embeddings are averaged) — and restart
the worker.

This only catches the voices on file — it is not a general TTS detector.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional

from ..config import settings

logger = logging.getLogger("carib.voice_match")

_AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".opus", ".m4a", ".flac", ".webm"}
_SAMPLE_RATE = 16000

_lock = threading.Lock()
_extractor = None
_refs: Optional[dict] = None  # name -> unit-norm embedding (np.ndarray)
_unavailable_reason: Optional[str] = None


def voice_name_from_file(filename: str) -> str:
    """'voice_preview_denzel - jamaican, raspy, and deep.mp3' -> 'denzel'."""
    stem = Path(filename).stem
    stem = re.sub(r"^voice_preview_", "", stem)
    return stem.split(" - ")[0].strip() or stem


def check_ai_voice(wav_path: str) -> dict:
    """Score a 16 kHz mono WAV against the known AI voices.

    Returns qc fields: ai_voice_score / ai_voice_closest / ai_voice_match
    (the matched name, or None). If the check can't run (model or refs
    missing) returns {"ai_voice_check": "unavailable: ..."} instead — QC
    carries on without it rather than failing the note.
    """
    if not settings.ai_voice_check_enabled:
        return {}
    if not _ensure_loaded():
        return {"ai_voice_check": f"unavailable: {_unavailable_reason}"}

    import soundfile as sf

    y, sr = sf.read(wav_path, dtype="float32", always_2d=False)
    if getattr(y, "ndim", 1) > 1:
        y = y.mean(axis=1)
    score, closest = best_match(_embed(y, sr), _refs)
    threshold = settings.ai_voice_match_threshold
    return {
        "ai_voice_score": round(score, 3),
        "ai_voice_closest": closest,
        "ai_voice_match": closest if score >= threshold else None,
    }


def best_match(embedding, refs: dict) -> tuple[float, str]:
    """Highest cosine similarity against unit-norm reference embeddings."""
    scores = {name: float(embedding @ ref) for name, ref in refs.items()}
    closest = max(scores, key=scores.get)
    return scores[closest], closest


def _ensure_loaded() -> bool:
    global _extractor, _refs, _unavailable_reason
    if _refs is not None:
        return True
    with _lock:
        if _refs is not None:
            return True
        if _unavailable_reason is not None:
            return False  # already failed once; don't retry per note
        try:
            _extractor = _load_extractor()
            _refs = _load_refs()
        except Exception as e:
            _unavailable_reason = str(e)
            logger.error("AI-voice check disabled: %s", e)
            return False
    logger.info("AI-voice check ready: %d reference voices", len(_refs))
    return True


def _load_extractor():
    model = settings.speaker_model_path
    if not os.path.isfile(model):
        raise RuntimeError(f"speaker model not found at {model}")
    import sherpa_onnx

    config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=model, num_threads=1)
    if not config.validate():
        raise RuntimeError(f"invalid speaker model config for {model}")
    return sherpa_onnx.SpeakerEmbeddingExtractor(config)


def _refs_dir() -> Path:
    if settings.ai_voice_refs_dir:
        return Path(settings.ai_voice_refs_dir)
    return Path(__file__).resolve().parents[2] / "data" / "ai-voices"


def group_reference_files(refs_dir: Path) -> dict[str, list[Path]]:
    """Voice name -> its clips.

    A loose file is one voice named after the file; a subdirectory is one
    voice named after the directory, with every audio file in it a clip.
    """
    def is_audio(p: Path) -> bool:
        return p.is_file() and p.suffix.lower() in _AUDIO_EXTS

    groups: dict[str, list[Path]] = {}
    for entry in sorted(refs_dir.iterdir()):
        if entry.is_dir():
            clips = sorted(p for p in entry.iterdir() if is_audio(p))
            if clips:
                groups.setdefault(entry.name, []).extend(clips)
        elif is_audio(entry):
            groups.setdefault(voice_name_from_file(entry.name), []).append(entry)
    return groups


def _load_refs() -> dict:
    import numpy as np

    refs_dir = _refs_dir()
    groups = group_reference_files(refs_dir) if refs_dir.is_dir() else {}
    if not groups:
        raise RuntimeError(f"no reference voices in {refs_dir}")
    refs = {}
    for name, clips in groups.items():
        # Mean of per-clip embeddings: steadier than any single short clip.
        mean = np.mean([_embed(*_decode(p)) for p in clips], axis=0)
        refs[name] = mean / (np.linalg.norm(mean) + 1e-12)
    return refs


def _decode(path: Path):
    import soundfile as sf

    fd, wav = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
             "-ac", "1", "-ar", str(_SAMPLE_RATE), wav],
            check=True, capture_output=True,
        )
        return sf.read(wav, dtype="float32")
    finally:
        os.remove(wav)


def _embed(y, sr: int):
    import numpy as np

    stream = _extractor.create_stream()
    stream.accept_waveform(sr, y)
    stream.input_finished()
    v = np.asarray(_extractor.compute(stream), dtype="float32")
    return v / (np.linalg.norm(v) + 1e-12)
