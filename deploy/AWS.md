# Deploying the backend on AWS (EC2 + Docker Compose)

The portal runs on Vercel; everything else runs on one EC2 host:

```
browser ──► Vercel (portal) ──/api/*──► https://API_DOMAIN ──► Caddy ──► backend (FastAPI)
Meta ─────────────────────────────────► https://API_DOMAIN/whatsapp/webhook
                                                              worker (QC) ◄─ Redis
                                                       RDS Postgres · S3 (audio)
```

Files: [`docker-compose.prod.yml`](../docker-compose.prod.yml), [`Caddyfile`](Caddyfile),
[`env.production.example`](env.production.example).

## 1. AWS resources

1. **IAM role** for the instance (EC2 → trusted entity), with an inline policy on the
   audio bucket:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"],
       "Resource": ["arn:aws:s3:::carib-voices-voicenotes", "arn:aws:s3:::carib-voices-voicenotes/*"]
     }]
   }
   ```
   With the role attached, leave `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` empty.
2. **EC2 instance**
   - Ubuntu 24.04 LTS, **t3.large** (2 vCPU / 8 GB). The QC worker loads
     faster-whisper and an ONNX speaker model; smaller instances run out of memory.
   - 30 GB gp3 root volume (Docker images are ~3 GB).
   - Attach the IAM role above.
   - **Security group:** inbound 80 and 443 from anywhere, 22 from your IP only.
     Do **not** open 8000, 5432 or 6379.
3. **Elastic IP** → associate with the instance, so the address survives restarts.
4. **DNS:** an `A` record for `api.yourdomain.com` → the Elastic IP.
5. **RDS Postgres 16**: `db.t4g.micro` to start, same VPC as the instance, not publicly
   accessible, security group allowing 5432 **only from the EC2 instance's security
   group**. Enable automated backups (7+ days retention). Put its endpoint in
   `DATABASE_URL` with `?sslmode=require`.

## 2. Install Docker on the instance

```bash
ssh ubuntu@<elastic-ip>
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu && exit   # log back in for the group to apply
```

## 3. Get the code and configure

```bash
git clone <repo-url> carib-voices && cd carib-voices
cp deploy/env.production.example .env
nano .env          # fill in every value — see comments in the file
```

`backend/data/ai-voices/` (the reference clips for the AI-voice check) must be in the
repo or copied onto the host before building — it's baked into the image.

## 4. Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

`migrate` runs `alembic upgrade head` once, then `backend` and `worker` start. Caddy
fetches the TLS certificate on first request (DNS must already resolve).

Check it:
```bash
curl https://api.yourdomain.com/health          # {"status":"ok",...}
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend worker
```

Seed phrases once, if the database is new:
```bash
docker compose -f docker-compose.prod.yml exec backend python -m app.seed_phrases
```

## 5. Point everything at it

| Where | Setting |
|---|---|
| Vercel → project env | `BACKEND_INTERNAL_URL=https://api.yourdomain.com` (then redeploy) |
| Meta → WhatsApp → Configuration | Callback URL `https://api.yourdomain.com/whatsapp/webhook`, verify token = `WHATSAPP_VERIFY_TOKEN`; `messages` field subscribed |
| Google Cloud → OAuth client | Authorized JavaScript origin = the Vercel/portal domain |
| `.env` on EC2 | `PORTAL_BASE_URL` and `CORS_ALLOW_ORIGINS` = the portal domain |

## Updating

```bash
cd ~/carib-voices && git pull
docker compose -f docker-compose.prod.yml up -d --build
```
Migrations run automatically on each `up`.
