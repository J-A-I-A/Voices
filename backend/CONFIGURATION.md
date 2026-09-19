# Backend configuration

All variables live in the root `.env.example` and are loaded by `app/config.py`.

## WhatsApp (Meta Cloud API)
| Variable | Notes |
|----------|-------|
| `WHATSAPP_TOKEN` | Permanent or temp access token from Meta App > WhatsApp > API Setup. |
| `WHATSAPP_PHONE_NUMBER_ID` | The phone number id from the API Setup tab. |
| `WHATSAPP_VERIFY_TOKEN` | Any string you choose; set the same value in the Meta webhook subscription. |
| `WHATSAPP_APP_SECRET` | App Secret from App settings; used to verify `X-Hub-Signature-256`. If unset, signature verification is skipped (dev only). |
| `AGENT_WHATSAPP_NUMBER` | Digits-only E.164 of the agent's number (no `+`), used in `wa.me` links. |

## AWS / S3
| Variable | Notes |
|----------|-------|
| `S3_BUCKET` | Private bucket. Never make it public — audio is served via signed URLs only. |
| `AWS_REGION` | Bucket region. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Credentials with s3:PutObject + s3:GetObject on the bucket. |
| `S3_SIGNED_URL_EXPIRY_SECONDS` | Lifetime of presigned GET URLs (default 300s / 5 min). |

## ASR / QC
| Variable | Default | Notes |
|----------|---------|-------|
| `RUNPOD_ASR_ENDPOINT` | — | RunPod serverless endpoint id (e.g. `jaia-patois-asr`) **or** full URL. Left empty → faster-whisper fallback only. |
| `RUNPOD_API_KEY` | — | RunPod API key. |
| `FALLBACK_ASR_MODEL` | `small` | faster-whisper model size (`tiny`..`large-v3`). |
| `WER_ACCEPT_MAX` | `0.30` | WER ≤ this → auto-accept. |
| `WER_REJECT_MIN` | `0.60` | WER ≥ this → auto-reject. Middle band → `needs_review`. |
| `MIN_DURATION_S` | `1.0` | Reject shorter clips. |
| `MAX_DURATION_S` | `60.0` | Reject longer clips. |
| `MIN_VAD_RATIO` | `0.25` | Reject mostly-silent clips. |
| `MIN_SNR_DB` | `8.0` | Flag/clamp noisy clips (low SNR feeds into review weighting). |
| `MIN_LOUDNESS_DBFS` | `-40.0` | Reject too-quiet. |
| `MAX_LOUDNESS_DBFS` | `-3.0` | Reject too-hot. |
| `MAX_CLIPPING_RATIO` | `0.05` | Reject clipped. |

## Auth
| Variable | Notes |
|----------|-------|
| `JWT_SECRET` | Long random string; signs access tokens and peppers OTP hashes. |
| `GOOGLE_CLIENT_ID` | The OAuth client id (portal uses the public client id; backend verifies id tokens against it). |
| `GOOGLE_CLIENT_SECRET` | Used only if you add a server-side token exchange flow. |
| `REVIEWER_EMAILS` | Comma-separated emails auto-granted reviewer role on register/login. |

## OTP
`OTP_TTL_SECONDS` (600), `OTP_MAX_ATTEMPTS` (5), `OTP_RESEND_COOLDOWN_SECONDS` (60).

## QC lifecycle
```
received ──(Stage 1 fail)──▶ rejected (reason)
received ──(Stage 2)──▶ accepted | rejected | needs_review
needs_review ──(reviewer)──▶ accepted | rejected (+reason)
```

QC metadata persisted on `VoiceNote.qc`:
`transcript`, `wer`, `snr_db`, `duration_seconds`, `vad_ratio`,
`loudness_dbfs`, `clipping_ratio`, `qc_stage_failed`, `qc_reason`,
`asr_model`, `checked_at` (plus Stage 3 fields when implemented).

