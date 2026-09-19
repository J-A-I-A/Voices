# Carib Voices Portal

Next.js (App Router) + Tailwind + shadcn-style UI for the Carib Voices web portal.

## What's here

- **Auth screens built from the Watermelon UI `auth-07` block ("Design 7")** —
  `src/components/watermelon-ui/auth-07.tsx` is an `AuthShell` that preserves
  the auth-07 layout (split screen, branding header, centered title with motion
  stagger reveal, rounded-full inputs, dark gradient submit button) and is reused
  by the register, sign-in, and Google-completion screens.
- **Google sign-in** via Google's GSI library (`@/components/google.tsx`).
  After the Google id_token is obtained we route to a completion step that
  **always collects Date of Birth** (Google does not provide it) and pre-fills
  First/Last name from the Google profile claims (`given_name`/`family_name`)
  for confirmation.
- **WhatsApp verification modal** (`@/components/verify-modal.tsx`) — Jamaica-only
  (876/658) phone entry, 6-digit OTP, 60s resend cooldown, success → "Message the
  Agent" deep link.
- **Voice-notes dashboard** (`/dashboard`) — status badges (Received/Accepted/
  Rejected/Needs review), QC signals (WER match %, VAD ratio, SNR, loudness),
  inline audio via short-lived signed S3 URLs, filter chips, and a
  "Message the Agent" `wa.me` button. Users only ever see their own notes.
- **Reviewer interface** (`/reviewer`) — for users granted the reviewer role,
  resolves `needs_review` notes to accepted/rejected (+ reason).

## Run locally

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_BASE_URL + GOOGLE_CLIENT_ID
npm install
npm run dev      # http://localhost:3000
```

> Requires the FastAPI backend to be running (../backend) so the portal can call
> `/auth/*`, `/voice-notes`, and `/reviewer/*`.

## Environment

| Variable | Notes |
|----------|-------|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL, e.g. `http://localhost:8000`. |
| `NEXT_PUBLIC_GOOGLE_CLIENT_ID` | Google OAuth client id (same as backend `GOOGLE_CLIENT_ID`). Used for the Google sign-in button. |

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start the dev server. |
| `npm run build` | Production build. |
| `npm run start` | Serve the production build. |
| `npm run lint` | ESLint (next/core-web-vitals). |
| `npm run typecheck` | `tsc --noEmit`. |

## Notes

- The age gate (>= 18) is enforced **server-side** in the backend; the form also
  validates client-side for UX, but the server is the source of truth and
  derives age from `date_of_birth` at submission time.
- The Jamaica phone rule is enforced both client-side (`@/lib/phone.ts`) and
  server-side (`backend/app/security/phone.py`).
