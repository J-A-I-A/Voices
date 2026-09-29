"""Generate extra reference clips for the known-AI-voice check via ElevenLabs.

For every voice in data/ai-voices (loose preview files or voice folders), finds
the ElevenLabs voice of the same name, then synthesises the seed phrases in it:

    data/ai-voices/<voice>/NN.mp3     reference clips (used by QC)
    <holdout-dir>/<voice>/NN.mp3      held-out clips (for calibration only)

A loose `voice_preview_<voice>....mp3` is moved into its folder as preview.mp3.
Voice ids are recorded in data/ai-voices/manifest.json.

Needs ELEVENLABS_API_KEY in the environment or in the repo-root .env.

    python scripts/generate_ai_voice_samples.py list       # resolve voices; free, changes nothing
    python scripts/generate_ai_voice_samples.py generate --holdout-dir /tmp/holdout

`generate` adds library voices to the account's "My Voices" when needed
(uses voice slots) and spends TTS characters (about 700 per voice).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.seed_phrases import SEED_PHRASES  # noqa: E402
from app.services.voice_match import group_reference_files  # noqa: E402

API = "https://api.elevenlabs.io"
REFS_DIR = BACKEND / "data" / "ai-voices"
MANIFEST = REFS_DIR / "manifest.json"
MODEL_ID = "eleven_multilingual_v2"
REFERENCE_CLIPS = 4  # the rest of the clips are held out


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "")
    env_file = BACKEND.parent / ".env"
    if not key and env_file.is_file():
        for line in env_file.read_text().splitlines():
            if line.strip().startswith("ELEVENLABS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set (environment or repo-root .env).")
    return key


def clip_texts() -> list[str]:
    """Seed phrases in six ~120-char clips: varied content, ~2-3 phrases each."""
    phrases, clips, n = list(SEED_PHRASES), [], 6
    for i in range(n):
        clips.append(" ".join(phrases[i::n]))
    return clips


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def local_preview(clips: list[Path]) -> Path | None:
    for p in clips:
        if p.name.startswith("voice_preview_") or p.name == "preview.mp3":
            return p
    return None


def resolve(cx: httpx.Client, name: str, preview: Path | None) -> dict | None:
    """Find the voice: the account's own voices first, then the shared library.

    A candidate whose preview audio is byte-identical to our local preview is
    certain; otherwise the first exact-name match is returned, flagged unverified.
    """
    want = sha256(preview.read_bytes()) if preview else None
    candidates = []

    r = cx.get("/v1/voices")
    r.raise_for_status()
    for v in r.json().get("voices", []):
        if v["name"].split(" - ")[0].strip().lower() == name.lower():
            candidates.append({"voice_id": v["voice_id"], "name": v["name"], "owned": True,
                               "preview_url": v.get("preview_url")})

    r = cx.get("/v1/shared-voices", params={"search": name, "page_size": 50})
    r.raise_for_status()
    for v in r.json().get("voices", []):
        if v["name"].split(" - ")[0].strip().lower() == name.lower():
            candidates.append({"voice_id": v["voice_id"], "name": v["name"], "owned": False,
                               "public_owner_id": v.get("public_owner_id"),
                               "preview_url": v.get("preview_url")})

    for c in candidates:
        if want and c.get("preview_url"):
            try:
                if sha256(httpx.get(c["preview_url"], timeout=30).content) == want:
                    return {**c, "verified": True}
            except httpx.HTTPError:
                pass
    return {**candidates[0], "verified": False} if candidates else None


def add_to_account(cx: httpx.Client, v: dict) -> str:
    r = cx.post(f"/v1/voices/add/{v['public_owner_id']}/{v['voice_id']}",
                json={"new_name": v["name"]})
    r.raise_for_status()
    return r.json()["voice_id"]


def usable_library_voice(cx: httpx.Client, v: dict) -> str:
    """Library voices can often be used directly; add to My Voices only if not."""
    r = cx.post(f"/v1/text-to-speech/{v['voice_id']}", params={"output_format": "mp3_44100_128"},
                json={"text": "Test.", "model_id": MODEL_ID}, timeout=60)
    if r.is_success:
        return v["voice_id"]
    return add_to_account(cx, v)


def tts(cx: httpx.Client, voice_id: str, text: str) -> bytes:
    r = cx.post(f"/v1/text-to-speech/{voice_id}", params={"output_format": "mp3_44100_128"},
                json={"text": text, "model_id": MODEL_ID}, timeout=120)
    r.raise_for_status()
    return r.content


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["list", "generate"])
    ap.add_argument("--holdout-dir", type=Path)
    ap.add_argument("--allow-unverified", action="store_true",
                    help="generate for voices matched by name only")
    args = ap.parse_args()
    if args.command == "generate" and not args.holdout_dir:
        ap.error("generate needs --holdout-dir")

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {}
    cx = httpx.Client(base_url=API, headers={"xi-api-key": api_key()}, timeout=60)
    groups = group_reference_files(REFS_DIR)

    resolved = {}
    for name, clips in groups.items():
        v = resolve(cx, name, local_preview(clips))
        resolved[name] = v
        if not v:
            print(f"  {name:16s} NOT FOUND")
        else:
            tag = "verified" if v["verified"] else "NAME ONLY"
            where = "my voices" if v["owned"] else "library"
            print(f"  {name:16s} {tag:9s} {where:9s} {v['voice_id']}  ({v['name']})")
    if args.command == "list":
        return

    texts = clip_texts()
    for name, v in resolved.items():
        if not v or (not v["verified"] and not args.allow_unverified):
            print(f"skip {name}")
            continue
        try:
            voice_id = v["voice_id"] if v["owned"] else usable_library_voice(cx, v)
        except httpx.HTTPStatusError as e:
            print(f"skip {name}: {e.response.status_code} {e.response.text[:200]}")
            continue
        folder = REFS_DIR / name
        folder.mkdir(exist_ok=True)
        preview = local_preview(groups[name])
        if preview and preview.parent != folder:
            shutil.move(str(preview), folder / "preview.mp3")
        hold = args.holdout_dir / name
        hold.mkdir(parents=True, exist_ok=True)
        for i, text in enumerate(texts, 1):
            dest = (folder if i <= REFERENCE_CLIPS else hold) / f"{i:02d}.mp3"
            if not dest.exists():
                dest.write_bytes(tts(cx, voice_id, text))
        manifest[name] = {"voice_id": voice_id, "elevenlabs_name": v["name"],
                          "model_id": MODEL_ID}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"done {name}")


if __name__ == "__main__":
    main()
