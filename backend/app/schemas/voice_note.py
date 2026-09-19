"""Voice note + QC schemas."""
from __future__ import annotations

import datetime as _dt
from typing import Any, Optional, Literal

from pydantic import BaseModel, ConfigDict


class QCMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")
    transcript: Optional[str] = None
    wer: Optional[float] = None
    snr_db: Optional[float] = None
    duration_seconds: Optional[float] = None
    vad_ratio: Optional[float] = None
    loudness_dbfs: Optional[float] = None
    clipping_ratio: Optional[float] = None
    qc_stage_failed: Optional[str] = None
    qc_reason: Optional[str] = None
    asr_model: Optional[str] = None
    checked_at: Optional[_dt.datetime] = None


class VoiceNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    phrase_text: Optional[str] = None
    phrase_id: Optional[str] = None
    whatsapp_message_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    mime_type: Optional[str] = None
    status: str
    reject_reason: Optional[str] = None
    qc: Optional[dict[str, Any]] = None
    reviewed_at: Optional[_dt.datetime] = None
    reviewer_id: Optional[str] = None
    created_at: _dt.datetime
    audio_url: Optional[str] = None  # signed S3 URL, short-lived


class VoiceNoteListResponse(BaseModel):
    items: list[VoiceNoteOut]
    total: int


class ReviewResolveRequest(BaseModel):
    status: Literal["accepted", "rejected"]
    reject_reason: Optional[str] = None

    def model_post_init(self, __context) -> None:  # type: ignore[override]
        if self.status == "rejected" and not self.reject_reason:
            raise ValueError("reject_reason is required when status is rejected")

