"""ASR service.

Primary: JAIA's Jamaican-Patois ASR model served on a RunPod serverless endpoint
(best fit for Jamaican speech; QC results also feed back into the model).
Fallback: faster-whisper locally (general baseline).

Both transcribers accept audio bytes / a local path and return {text, model}.
"""
from __future__ import annotations

import base64
import logging
import os
import tempfile
from typing import Optional

import httpx

from ..config import settings

logger = logging.getLogger("carib.asr")


async def transcribe(audio_bytes: bytes, *, mime_type: str = "audio/ogg") -> dict:
    """Transcribe audio. Returns {"text", "model"}.

    Tries the RunPod serverless endpoint first; on any failure, falls back to
    faster-whisper locally.
    """
    try:
        text = await _runpod_transcribe(audio_bytes, mime_type)
        if text is not None:
            return {"text": text, "model": f"runpod:{settings.runpod_asr_endpoint}"}
    except Exception as e:
        logger.warning("RunPod ASR failed (%s); falling back to faster-whisper.", e)

    text = _faster_whisper_transcribe(audio_bytes, mime_type)
    return {"text": text, "model": f"faster-whisper:{settings.fallback_asr_model}"}


async def _runpod_transcribe(audio_bytes: bytes, mime_type: str) -> Optional[str]:
    if not settings.runpod_asr_endpoint or not settings.runpod_api_key:
        logger.info("RunPod ASR not configured; skipping primary recognizer.")
        return None

    endpoint = settings.runpod_asr_endpoint
    if not endpoint.startswith("http"):
        # RunPod serverless endpoint id → public URL.
        endpoint = f"https://api.runpod.ai/v2/{endpoint}/run"
    else:
        if endpoint.rstrip("/").endswith("/runsync"):
            endpoint = endpoint.rstrip("/")[:-len("runsync")] + "run"
        elif not endpoint.rstrip("/").endswith("/run"):
            endpoint = endpoint.rstrip("/") + "/run"

    payload_b64 = base64.b64encode(audio_bytes).decode()
    body = {
        "input": {
            "audio_base64": payload_b64,
            "mime_type": mime_type,
        }
    }
    headers = {"Authorization": f"Bearer {settings.runpod_api_key}"}
    async with httpx.AsyncClient(timeout=180) as cx:
        # RunPod /run is async: it returns a job id; poll /status/:id.
        r = await cx.post(endpoint, json=body, headers=headers)
        r.raise_for_status()
        j = r.json()
        if j.get("status") == "COMPLETED":
            return _extract_text(j.get("output"))
        job_id = j.get("id")
        if not job_id:
            raise RuntimeError("RunPod returned no job id")
        status_url = f"{endpoint.rsplit('/run', 1)[0]}/status/{job_id}"
        # Poll for completion (bounded).
        import asyncio, time
        deadline = time.time() + 170
        while time.time() < deadline:
            await asyncio.sleep(2)
            sr = await cx.get(status_url, headers=headers)
            sr.raise_for_status()
            sj = sr.json()
            st = sj.get("status")
            if st == "COMPLETED":
                return _extract_text(sj.get("output"))
            if st in ("FAILED", "CANCELLED", "TIMED_OUT"):
                raise RuntimeError(f"RunPod job {st}")
        raise TimeoutError("RunPod job timed out")


def _extract_text(output) -> Optional[str]:
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, dict):
        return (output.get("text") or output.get("transcript") or "").strip() or None
    return None


_fwhisper_cache = {"model": None}


def _get_faster_whisper():
    if _fwhisper_cache["model"] is not None:
        return _fwhisper_cache["model"]
    from faster_whisper import WhisperModel  # local import; heavy.
    model = WhisperModel(settings.fallback_asr_model, device="cpu", compute_type="int8")
    _fwhisper_cache["model"] = model
    return model


def _faster_whisper_transcribe(audio_bytes: bytes, mime_type: str) -> str:
    """Transcribe with faster-whisper. Converts bytes to a wav via ffmpeg first."""
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=_ext_for(mime_type), delete=False) as f:
        f.write(audio_bytes)
        src = f.name
    wav = src + ".wav"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", wav],
            check=True, capture_output=True,
        )
        model = _get_faster_whisper()
        segments, _info = model.transcribe(wav, beam_size=1, language="en")
        return " ".join(s.text for s in segments).strip()
    finally:
        for p in (src, wav):
            try:
                os.remove(p)
            except OSError:
                pass


def _ext_for(mime: str) -> str:
    return {
        "audio/ogg": ".ogg",
        "audio/ogg; codecs=opus": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/webm": ".webm",
        "audio/wav": ".wav",
    }.get(mime, ".bin")
