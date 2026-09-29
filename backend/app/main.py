"""FastAPI application entrypoint for Carib Voices."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import (
    auth_router, whatsapp_router, voice_notes_router,
    reviewer_router, phrases_router, admin_router, profile_router,
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Carib Voices API",
    version="0.1.0",
    description="WhatsApp voice-note collection portal + QC pipeline for Jamaican speech data.",
)

# CORS: CORS_ALLOW_ORIGINS, default "*". The portal proxies /api/* through its
# own origin so it doesn't need CORS at all; this only matters for direct
# browser calls. Auth is a Bearer token, not cookies, so credentials stay off —
# browsers reject "*" combined with allow_credentials=True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(phrases_router)
app.include_router(voice_notes_router)
app.include_router(reviewer_router)
app.include_router(admin_router)
app.include_router(profile_router)
app.include_router(whatsapp_router)


@app.get("/", include_in_schema=False)
async def root():
    return {"name": "Carib Voices API", "status": "ok"}


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok", "version": app.version}

