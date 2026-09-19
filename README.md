# Carib Voices

A production-ready application for **collecting voice notes from verified Jamaican users over WhatsApp**, storing each recording in Amazon S3, linking it to the user's portal account, running automated quality control (QC), and letting users track review status.

It has two tightly-linked components:

1. **WhatsApp Agent** — a FastAPI webhook that talks the Meta WhatsApp Cloud API. Verified users message the agent, receive a phrase, read it aloud, and the resulting voice note is stored, QC'd, and linked to their account.
2. **Web Portal** — a Next.js + Tailwind + shadcn/ui app (styled with the Watermelon `auth-07) block) where users register (Google **or** email+password), verify a Jamaican WhatsApp number via OTP, and track the status of every voice-note submission through an inline audio dashboard. A minimal reviewer interface resolves `needs_review` notes.

## Architecture

```
┌──────────────┐        ┌────────────────────┐        ┌────────────┐
│  Portal (Vercel) │    │  FastAPI backend       │     │  PostgreSQL │
│  Next.js+Auth    │◀──▶│  /auth /api /whatsapp   │◀──▶│  (tables)  │
└──────────────┘        └─────────┬──────────┘        └────────────┘
                                  │
              ┌───────────────────┼────────────────────┐
              ▼                   ▼                    ▼
        Meta WhatsApp         Amazon S3            QC worker
        Cloud API             (private bucket,     (ffmpeg / librosa / VAD /
        (Graph + webhooks)     signed URLs)         RunPod ASR / jiwer WER)
```

## Repo layout

```
Carib Voices/
├── backend/                 # FastAPI service + QC worker
│   ├── app/
│   │   ├── main.py           # FastAPI entry, router registration
│   │   ├── config.py         # Settings (env-driven)
│   │   ├── db.py             # SQLAlchemy engine + session
│   │   ├── models/           # ORM models
│   │   ├── routers/          # auth, voice_notes, whatsapp, reviewer
│   │   ├── schemas/          # Pydantic request/response models
│   │   ├── services/         # whatsapp, s3, asr, qc, otp, rate_limit
│   │   ├── security/         # phone validation, age gate, hashing, jwt
│   │   ├── workers/          # QC background worker (async)
│   │   └── worker_main.py    # Standalone QC worker entrypoint
│   ├── migrations/           # Alembic migrations
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── portal/                  # Next.js portal
│   ├── src/
│   │   ├── components/
│   │   │   ├── watermelon-ui/auth-07.tsx   # Adapted Watermelon block
│   │   │   └── ui/                          # shadcn/ui primitives
│   │   ├── lib/api.ts        # Typed API client
│   │   ├── lib/phone.ts      # Jamaica phone normalization
│   │   └── app/              # App-router pages
│   ├── package.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml        # Postgres + backend + worker for local dev
├── .env.example              # All env vars (see Configuration)
└── README.md
```

## Quick start (local dev)

Prerequisites: Docker + Docker Compose. (Node 20+ only if you run the portal
natively instead — see "Portal natively" below.)

### All-in-Docker (one command)

```bash
# 1. Configure environment
cp .env.example .env
#   fill in WHATSAPP_*, AWS_*, GOOGLE_* at minimum; DB & POSTGRES are pre-set for compose
cp portal/.env.local.example portal/.env.local   # NEXT_PUBLIC_API_BASE_URL is set by compose

# 2. Start Postgres + Redis + backend + QC worker + portal (builds images once)
docker compose up --build

# 3. In another terminal, apply the schema + seed the phrase bank (once)
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.seed_phrases
```

- Portal → http://localhost:3000
- Backend → http://localhost:8000 (interactive docs at `/docs`)
- The portal container bind-mounts `./portal` so edits hot-reload (HMR) inside the container.

### Portal natively (alternative — best HMR on host filesystems)

If you prefer faster HMR on a host filesystem, run everything except the portal in
Docker and the portal on the host:

```bash
docker compose up --build db redis backend worker   # no portal

cd portal
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm install && npm run dev
```

> For WhatsApp webhook testing without a public URL, use `ngrok http 8000`
> and point your Meta app's webhook to `https://<your-ngrok>.ngrok.app/whatsapp/webhook`.

## Configuration / environment variables

All variables are defined and documented in [`.env.example`](./.env.example). Summary:

| Group        | Variables |
|--------------|-----------|
| WhatsApp     | `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`, `AGENT_WHATSAPP_NUMBER` |
| AWS / S3     | `S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` |
| ASR / QC     | `RUNPOD_ASR_ENDPOINT`, `RUNPOD_API_KEY`, `WER_ACCEPT_MAX`, `WER_REJECT_MIN`, `MIN_DURATION_S`, `MAX_DURATION_S`, `MIN_VAD_RATIO`, `MIN_SNR_DB` |
| Auth         | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET` |
| App          | `DATABASE_URL`, `PORTAL_BASE_URL` |

See [backend/CONFIGURATION.md](./backend/CONFIGURATION.md) for per-variable notes and the QC threshold defaults.

## Assumptions & decisions

- **Age gate = ≥ 18.** Age is derived from `date_of_birth` at read time and never persisted as a static number, so returning users age correctly. Enforced server-side.
- **Jamaica-only WhatsApp numbers.** Accepts flexible input; normalized to E.164 necessarily `+1876XXXXXXX` or `+1658XXXXXXX` (Jamaica's NANP area codes). Any other area code/country is rejected.
- **OTP security.** 6-digit codes hashed at rest, 10-minute expiry, max 5 attempts, 60-second resend cooldown, IP+phone rate limiting.
- ** QC strategy.** Stage 1 fast structural checks (ffmpeg/librosa + WebRTC VAD) run synchronously and fail fast; Stage 2 content check (ASR on a RunPod serverless endpoint + jiwer WER) runs only on survivors. JAIA's Patois ASR is the primary recognizer; `faster-whisper` is the fallback. The jaia package used here is the JAIA Jamaican-Patois ASR module referenced from RunPod.
- **Stage 3 ML checks (language ID, single-speaker/diarization, duplicate fingerprint, synthetic/replay detection) are designed for with extension points in `workers/qc.py` but not built in the first pass.**
- **S3 audio is private** and served only via short-lived signed URLs; a user can never read another user's notes.
- **Reviewer interface.** Notes in the middle WER band land in `needs_review`; signed-in users with `is_reviewer=True` can set `accepted`/`rejected` + reason. Most notes resolve automatically.
- **Multi-country support, payments, and mobile native apps are out of scope.**

## Testing

The backend ships with a focused test suite (no Postgres required — it runs on
in-memory SQLite via FastAPI's `TestClient` + `dependency_overrides`):

```bash
cd backend
python -m venv .venv && . .venv/bin/activate

# Lightweight (no C toolchain needed): the QC-audio test skips without librosa.
pip install pytest pytest-asyncio pydantic pydantic-settings sqlalchemy alembic \
            "python-jose[cryptography]" "passlib[bcrypt]" "bcrypt<5" email-validator \
            fastapi "uvicorn[standard]" httpx boto3 "python-multipart" "psycopg[binary]" redis arq
pytest            # 34 passed, 1 skipped

# Full install (pulls librosa/webrtcvad/faster-whisper; needs build-essential for
# webrtcvad's wheel — the Dockerfile installs it): pip install -e ".[dev]"
```

Coverage:

- **Security logic** — Jamaica phone normalization (876/658 only, E.164), age gate
  (≥ 18 boundary), OTP hashing, WER normalization + three-way QC decision.
- **Auth flow** — register, under-18 rejected server-side, non-Jamaican number
  rejected, full OTP verify, agent-link + voice-notes gated behind verification.
- **WhatsApp webhook** — verify-token handshake, `X-Hub-Signature-256` signature
  accept/reject.
- **Inbound agent** — unknown sender → register guidance; text → phrase assigned;
  voice note → S3 upload under `voicenotes/{user_id}/{uuid}.ogg`, `received`
  record linked to phrase + message id, QC enqueued, confirmation sent.

The portal type-checks and builds cleanly:

```bash
cd portal
npm install
npm run typecheck   # tsc --noEmit  (0 errors)
npm run build       # next build (9 routes, no warnings)
```

## License

Proprietary. © Carib Voices.

